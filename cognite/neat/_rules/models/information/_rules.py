import math
import sys
from collections.abc import Hashable
from typing import TYPE_CHECKING, Any, ClassVar

import pandas as pd
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import SerializationInfo
from rdflib import Namespace, URIRef

from cognite.neat._constants import get_default_prefixes
from cognite.neat._issues.errors import NeatValueError, PropertyDefinitionError
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models._base_rules import (
    BaseMetadata,
    BaseRules,
    ClassRef,
    DataModelAspect,
    PropertyRef,
    RoleTypes,
    SheetList,
    SheetRow,
)
from cognite.neat._rules.models._rdfpath import (
    RDFPath,
    TransformationRuleType,
    parse_rule,
)
from cognite.neat._rules.models._types import (
    ClassEntityType,
    InformationPropertyType,
    MultiValueTypeType,
)
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ClassEntityList,
    Entity,
    MultiValueTypeInfo,
    Undefined,
    UnknownEntity,
)

if TYPE_CHECKING:
    from cognite.neat._rules.models import DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information
    aspect: ClassVar[DataModelAspect] = DataModelAspect.logical

    # Linking to Conceptual and Physical data model aspects
    physical: URIRef | None = Field(None, description="Link to the logical data model aspect")
    conceptual: URIRef | None = Field(None, description="Link to the logical data model aspect")


def _get_metadata(context: Any) -> InformationMetadata | None:
    if isinstance(context, dict) and isinstance(context.get("metadata"), InformationMetadata):
        return context["metadata"]
    return None


class InformationClass(SheetRow):
    """
    Class is a category of things that share a common set of attributes and relationships.

    Args:
        class_: The class ID of the class.
        description: A description of the class.
        implements: Which classes the current class implements.
    """

    class_: ClassEntityType = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    implements: ClassEntityList | None = Field(alias="Implements", default=None)

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.class_,)

    @field_serializer("class_", when_used="unless-none")
    def remove_default_prefix(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _get_metadata(info.context)) and isinstance(value, Entity):
            return value.dump(prefix=metadata.prefix, version=metadata.version)
        return str(value)

    @field_serializer("implements", when_used="unless-none")
    def remove_default_prefixes(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _get_metadata(info.context)):
            return ",".join(
                (
                    class_.dump(prefix=metadata.prefix, version=metadata.version)
                    if isinstance(class_, Entity)
                    else str(class_)
                )
                for class_ in value
            )
        return ",".join(str(value) for value in value)

    def as_reference(self) -> ClassRef:
        return ClassRef(Class=self.class_)


class InformationProperty(SheetRow):
    """
    A property is a characteristic of a class. It is a named attribute of a class that describes a range of values
    or a relationship to another class.

    Args:
        class_: Class ID to which property belongs
        property_: Property ID of the property
        name: Property name.
        value_type: Type of value property will hold (data or link to another class)
        min_count: Minimum count of the property values. Defaults to 0
        max_count: Maximum count of the property values. Defaults to None
        default: Default value of the property
        transformation: Actual rule for the transformation from source to target representation of
              knowledge graph. Defaults to None (no transformation)
    """

    class_: ClassEntityType = Field(alias="Class")
    property_: InformationPropertyType = Field(alias="Property")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    value_type: DataType | ClassEntityType | MultiValueTypeType | UnknownEntity = Field(
        alias="Value Type", union_mode="left_to_right"
    )
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)
    transformation: RDFPath | None = Field(alias="Transformation", default=None)
    inherited: bool = Field(
        default=False,
        exclude=True,
        alias="Inherited",
        description="Flag to indicate if the property is inherited, only use for internal purposes",
    )

    def _identifier(self) -> tuple[Hashable, ...]:
        return self.class_, self.property_

    @field_validator("max_count", mode="before")
    def parse_max_count(cls, value: int | float | None) -> int | float | None:
        if value is None:
            return float("inf")
        return value

    @field_validator("transformation", mode="before")
    def generate_rdfpath(cls, value: str | RDFPath | None) -> RDFPath | None:
        if value is None or isinstance(value, RDFPath):
            return value
        elif isinstance(value, str):
            return parse_rule(value, TransformationRuleType.rdfpath)
        else:
            raise NeatValueError(f"Invalid RDF Path: {value!s}")

    @model_validator(mode="after")
    def set_default_as_list(self):
        if (
            self.type_ == EntityTypes.data_property
            and self.default
            and self.is_list
            and not isinstance(self.default, list)
        ):
            if isinstance(self.default, str):
                if self.default:
                    self.default = self.default.replace(", ", ",").split(",")
                else:
                    self.default = [self.default]
        return self

    @model_validator(mode="after")
    def set_type_for_default(self):
        if self.type_ == EntityTypes.data_property and self.default:
            default_value = self.default[0] if isinstance(self.default, list) else self.default

            if type(default_value) is not self.value_type.python:
                try:
                    if isinstance(self.default, list):
                        updated_list = []
                        for value in self.default:
                            updated_list.append(self.value_type.python(value))
                        self.default = updated_list
                    else:
                        self.default = self.value_type.python(self.default)

                except Exception:
                    raise PropertyDefinitionError(
                        self.class_,
                        "Class",
                        self.property_,
                        f"Default value {self.default} is not of type {self.value_type.python}",
                    ) from None
        return self

    @field_serializer("max_count", when_used="json-unless-none")
    def serialize_max_count(self, value: int | float | None) -> int | float | None | str:
        if isinstance(value, float) and math.isinf(value):
            return None
        return value

    @field_serializer("class_", "value_type", when_used="unless-none")
    def remove_default_prefix(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _get_metadata(info.context)) and isinstance(value, Entity):
            return value.dump(prefix=metadata.prefix, version=metadata.version)
        return str(value)

    @property
    def type_(self) -> EntityTypes:
        """Type of property based on value type. Either data (attribute) or object (edge) property."""
        if isinstance(self.value_type, DataType):
            return EntityTypes.data_property
        elif isinstance(self.value_type, ClassEntity):
            return EntityTypes.object_property
        else:
            return EntityTypes.undefined

    @property
    def is_mandatory(self) -> bool:
        """Returns True if property is mandatory."""
        return self.min_count not in {0, None}

    @property
    def is_list(self) -> bool:
        """Returns True if property contains a list of values."""
        return self.max_count in {float("inf"), None} or (
            isinstance(self.max_count, int | float) and self.max_count > 1
        )

    def as_reference(self) -> PropertyRef:
        return PropertyRef(Class=self.class_, Property=self.property_)


class InformationRules(BaseRules):
    metadata: InformationMetadata = Field(alias="Metadata")
    properties: SheetList[InformationProperty] = Field(alias="Properties")
    classes: SheetList[InformationClass] = Field(alias="Classes")
    prefixes: dict[str, Namespace] = Field(default_factory=get_default_prefixes, alias="Prefixes")

    @field_validator("prefixes", mode="before")
    def parse_str(cls, values: Any) -> Any:
        if isinstance(values, dict):
            return {key: Namespace(value) if isinstance(value, str) else value for key, value in values.items()}
        elif values is None:
            values = get_default_prefixes()
        return values

    @model_validator(mode="after")
    def update_entities_prefix(self) -> Self:
        # update expected_value_types
        for property_ in self.properties:
            if isinstance(property_.value_type, ClassEntity) and property_.value_type.prefix is Undefined:
                property_.value_type.prefix = self.metadata.prefix

            if isinstance(property_.value_type, MultiValueTypeInfo):
                property_.value_type.set_default_prefix(self.metadata.prefix)

            if property_.class_.prefix is Undefined:
                property_.class_.prefix = self.metadata.prefix

        # update implements
        for class_ in self.classes:
            if class_.implements:
                for parent in class_.implements:
                    if not isinstance(parent.prefix, str):
                        parent.prefix = self.metadata.prefix
            if class_.class_.prefix is Undefined:
                class_.class_.prefix = self.metadata.prefix

        return self

    @model_validator(mode="after")
    def post_validation(self) -> "InformationRules":
        from ._validation import InformationPostValidation

        issue_list = InformationPostValidation(self).validate()
        if issue_list.warnings:
            issue_list.trigger_warnings()
        if issue_list.has_errors:
            raise issue_list.as_exception()
        return self

    def as_dms_rules(self) -> "DMSRules":
        from cognite.neat._rules.transformers._converters import _InformationRulesConverter

        return _InformationRulesConverter(self).as_dms_rules()

    def _repr_html_(self) -> str:
        summary = {
            "type": "Logical Data Model",
            "intended for": "Information Architect",
            "name": self.metadata.name,
            "external_id": self.metadata.external_id,
            "version": self.metadata.version,
            "classes": len(self.classes),
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
