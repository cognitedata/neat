import math
from collections.abc import Hashable
from typing import TYPE_CHECKING, Any, ClassVar

import pandas as pd
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import SerializationInfo
from rdflib import Namespace, URIRef

from cognite.neat.core._constants import get_default_prefixes_and_namespaces
from cognite.neat.core._data_model._constants import EntityTypes
from cognite.neat.core._data_model.models._base_verified import (
    BaseVerifiedDataModel,
    BaseVerifiedMetadata,
    DataModelLevel,
    RoleTypes,
    SheetList,
    SheetRow,
)
from cognite.neat.core._data_model.models._types import (
    ConceptEntityType,
    ConceptualPropertyType,
    MultiValueTypeType,
    URIRefType,
)

# NeatIdType,
from cognite.neat.core._data_model.models.data_types import DataType
from cognite.neat.core._data_model.models.entities import (
    ClassEntityList,
    ConceptEntity,
    ConceptualEntity,
    UnknownEntity,
)
from cognite.neat.core._issues.errors import PropertyDefinitionError

if TYPE_CHECKING:
    from cognite.neat.core._data_model.models import PhysicalDataModel


class ConceptualMetadata(BaseVerifiedMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information
    level: ClassVar[DataModelLevel] = DataModelLevel.conceptual

    # Linking to Conceptual and Physical data model aspects
    physical: URIRef | str | None = Field(None, description="Link to the physical data model level")


def _get_metadata(context: Any) -> ConceptualMetadata | None:
    if isinstance(context, dict) and isinstance(context.get("metadata"), ConceptualMetadata):
        return context["metadata"]
    return None


class Concept(SheetRow):
    """
    Concept is a category of things that share a common set of attributes and relationships.

    Args:
        concept: An ID of the concept.
        description: A description of the class.
        implements: Which classes the current class implements.
    """

    concept: ConceptEntityType = Field(
        alias="Concept",
        description="Concept id being defined, use strongly advise `PascalCase` usage.",
    )
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the class.")
    description: str | None = Field(alias="Description", default=None, description="Short description of the class.")
    implements: ClassEntityList | None = Field(
        alias="Implements",
        default=None,
        description="List of classes (comma separated) that the current class implements (parents).",
    )
    instance_source: URIRefType | None = Field(
        alias="Instance Source",
        default=None,
        description="The link to to the rdf.type that have the instances for this class.",
    )
    physical: URIRefType | None = Field(
        None,
        description="Link to the class representation in the physical data model aspect",
    )

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.concept,)

    @field_serializer("concept", when_used="unless-none")
    def remove_default_prefix(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _get_metadata(info.context)) and isinstance(value, ConceptualEntity):
            return value.dump(prefix=metadata.prefix, version=metadata.version)
        return str(value)

    @field_serializer("implements", when_used="unless-none")
    def remove_default_prefixes(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _get_metadata(info.context)):
            return ",".join(
                (
                    concept.dump(prefix=metadata.prefix, version=metadata.version)
                    if isinstance(concept, ConceptualEntity)
                    else str(concept)
                )
                for concept in value
            )
        return ",".join(str(value) for value in value)


class ConceptualProperty(SheetRow):
    """
    A property is a characteristic of a concept. It is a named attribute of a concept
    that describes a range of values or a relationship to another concept.

    Args:
        concept: Concept ID to which property belongs
        property_: Property ID of the property
        name: Property name.
        value_type: Type of value property will hold (data or link to another class)
        min_count: Minimum count of the property values. Defaults to 0
        max_count: Maximum count of the property values. Defaults to None
        default: Default value of the property
        instance_source: Actual rule for the transformation from source to target representation of
              knowledge graph. Defaults to None (no transformation)
    """

    concept: ConceptEntityType | UnknownEntity = Field(
        alias="Concept",
        description="Concept id that the property is defined for, strongly advise `PascalCase` usage.",
    )
    property_: ConceptualPropertyType = Field(
        alias="Property",
        description="Property id, strongly advised to `camelCase` usage.",
    )
    name: str | None = Field(alias="Name", default=None, description="Human readable name of the property.")
    description: str | None = Field(alias="Description", default=None, description="Short description of the property.")
    value_type: DataType | ConceptEntityType | MultiValueTypeType | UnknownEntity = Field(
        alias="Value Type",
        union_mode="left_to_right",
        description="Value type that the property can hold. It takes either subset of XSD type or a class defined.",
    )
    min_count: int | None = Field(
        alias="Min Count",
        default=None,
        description="Minimum number of values that the property can hold. "
        "If no value is provided, the default value is  `0`, "
        "which means that the property is optional.",
    )
    max_count: int | float | None = Field(
        alias="Max Count",
        default=None,
        description="Maximum number of values that the property can hold. "
        "If no value is provided, the default value is  `inf`, "
        "which means that the property can hold any number of values (listable).",
    )
    default: Any | None = Field(alias="Default", default=None, description="Default value of the property.")
    instance_source: list[URIRefType] | None = Field(
        alias="Instance Source",
        default=None,
        description="The URIRef(s) in the graph to get the value of the property.",
    )
    inherited: bool = Field(
        default=False,
        exclude=True,
        alias="Inherited",
        description="Flag to indicate if the property is inherited, only use for internal purposes",
    )

    physical: URIRefType | None = Field(
        None,
        description="Link to the class representation in the physical data model aspect",
    )

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.concept, self.property_

    @field_validator("max_count", mode="before")
    def parse_max_count(cls, value: int | float | None) -> int | float | None:
        if value is None:
            return float("inf")
        return value

    @field_validator("instance_source", mode="before")
    def split_on_comma(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        return value

    @model_validator(mode="after")
    def set_type_for_default(self) -> Any:
        if self.type_ == EntityTypes.data_property and self.default:
            default_value = self.default[0] if isinstance(self.default, list) else self.default

            if type(default_value) is not self.value_type.python:  # type: ignore
                try:
                    if isinstance(self.default, list):
                        updated_list = []
                        for value in self.default:
                            updated_list.append(self.value_type.python(value))  # type: ignore
                        self.default = updated_list
                    else:
                        self.default = self.value_type.python(self.default)  # type: ignore

                # this value_type.python does not seems correct. Need to check this further
                except Exception:
                    raise PropertyDefinitionError(
                        self.concept,
                        "Class",
                        self.property_,
                        f"Default value {self.default} is not of type {self.value_type.python}",  # type: ignore
                    ) from None
        return self

    @field_serializer("instance_source", when_used="unless-none")
    def serialize_instance_source(self, value: list[URIRefType] | None) -> str | None:
        if value is None:
            return None
        return ",".join(str(v) for v in value)

    @field_serializer("max_count", when_used="json-unless-none")
    def serialize_max_count(self, value: int | float | None) -> int | float | None | str:
        if isinstance(value, float) and math.isinf(value):
            return None
        return value

    @field_serializer("concept", "value_type", when_used="unless-none")
    def remove_default_prefix(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _get_metadata(info.context)) and isinstance(value, ConceptualEntity):
            return value.dump(prefix=metadata.prefix, version=metadata.version)
        return str(value)

    @property
    def type_(self) -> EntityTypes:
        """Type of property based on value type. Either data (attribute) or object (edge) property."""
        if isinstance(self.value_type, DataType):
            return EntityTypes.data_property
        elif isinstance(self.value_type, ConceptEntity):
            return EntityTypes.object_property
        else:
            return EntityTypes.undefined


class ConceptualDataModel(BaseVerifiedDataModel):
    metadata: ConceptualMetadata = Field(alias="Metadata", description="Metadata for the conceptual data model")
    concepts: SheetList[Concept] = Field(alias="Concepts", description="List of concepts")
    properties: SheetList[ConceptualProperty] = Field(
        alias="Properties", default_factory=SheetList, description="List of properties"
    )
    prefixes: dict[str, Namespace] = Field(
        alias="Prefixes",
        default_factory=get_default_prefixes_and_namespaces,
        description="the definition of the prefixes that are used in the conceptual data model",
    )

    @field_validator("prefixes", mode="before")
    def parse_str(cls, values: Any) -> Any:
        if isinstance(values, dict):
            return {key: Namespace(value) if isinstance(value, str) else value for key, value in values.items()}
        elif values is None:
            values = get_default_prefixes_and_namespaces()
        return values

    @model_validator(mode="after")
    def set_neat_id(self) -> "ConceptualDataModel":
        namespace = self.metadata.namespace

        for concept in self.concepts:
            if not concept.neatId:
                concept.neatId = namespace[concept.concept.suffix]
        for property_ in self.properties:
            if not property_.neatId:
                property_.neatId = namespace[f"{property_.concept.suffix}/{property_.property_}"]

        return self

    def update_neat_id(self) -> None:
        """Update neat ids"""

        namespace = self.metadata.namespace

        for concept in self.concepts:
            concept.neatId = namespace[concept.concept.suffix]
        for property_ in self.properties:
            property_.neatId = namespace[f"{property_.concept.suffix}/{property_.property_}"]

    def sync_with_physical_data_model(self, physical_data_model: "PhysicalDataModel") -> None:
        # Sync at the metadata level
        if physical_data_model.metadata.conceptual == self.metadata.identifier:
            self.metadata.physical = physical_data_model.metadata.identifier
        else:
            # if models are not linked to start with, we skip
            return None

        conceptual_properties_by_neat_id = {prop.neatId: prop for prop in self.properties}
        physical_properties_by_neat_id = {prop.neatId: prop for prop in physical_data_model.properties}
        for neat_id, prop in physical_properties_by_neat_id.items():
            if prop.conceptual in conceptual_properties_by_neat_id:
                conceptual_properties_by_neat_id[prop.conceptual].physical = neat_id

        classes_by_neat_id = {cls.neatId: cls for cls in self.concepts}
        views_by_neat_id = {view.neatId: view for view in physical_data_model.views}
        for neat_id, view in views_by_neat_id.items():
            if view.conceptual in classes_by_neat_id:
                classes_by_neat_id[view.conceptual].physical = neat_id

    def as_physical_data_model(self) -> "PhysicalDataModel":
        from cognite.neat.core._data_model.transformers._converters import (
            _ConceptualDataModelConverter,
        )

        return _ConceptualDataModelConverter(self).as_physical_data_model()

    @classmethod
    def display_type_name(cls) -> str:
        return "VerifiedConceptualDataModel"

    def _repr_html_(self) -> str:
        summary = {
            "level": self.metadata.level,
            "intended for": "Domain Expert and/or Information Architect",
            "name": self.metadata.name,
            "external_id": self.metadata.external_id,
            "version": self.metadata.version,
            "concepts": len(self.concepts),
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
