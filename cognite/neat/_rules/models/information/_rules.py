import math
import sys
from collections.abc import Hashable
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

import pandas as pd
from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_core.core_schema import SerializationInfo
from rdflib import Namespace

from cognite.neat._constants import get_default_prefixes
from cognite.neat._issues.errors import NeatValueError, PropertyDefinitionError
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models._base_rules import (
    BaseMetadata,
    BaseRules,
    ClassRef,
    DataModelType,
    ExtensionCategory,
    ExtensionCategoryType,
    MatchType,
    PropertyRef,
    RoleTypes,
    SchemaCompleteness,
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
    NamespaceType,
    PrefixType,
    StrListType,
    VersionType,
)
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ClassEntityList,
    Entity,
    MultiValueTypeInfo,
    ReferenceEntity,
    Undefined,
    UnknownEntity,
    URLEntity,
)

if TYPE_CHECKING:
    from cognite.neat._rules.models import DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information
    data_model_type: DataModelType = Field(DataModelType.enterprise, alias="dataModelType")
    schema_: SchemaCompleteness = Field(SchemaCompleteness.partial, alias="schema")
    extension: ExtensionCategoryType | None = ExtensionCategory.addition

    prefix: PrefixType
    namespace: NamespaceType

    name: str = Field(
        alias="title",
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )
    description: str | None = Field(None, min_length=1, max_length=1024)
    version: VersionType

    created: datetime = Field(
        description=("Date of the data model creation"),
    )

    updated: datetime = Field(
        description=("Date of the data model update"),
    )
    creator: StrListType = Field(
        description=(
            "List of contributors to the data model creation, "
            "typically information architects are considered as contributors."
        ),
    )
    license: str | None = None
    rights: str | None = None

    @model_validator(mode="after")
    def extension_none_but_schema_extend(self) -> Self:
        if self.extension is None:
            self.extension = ExtensionCategory.addition
            return self
        return self

    @field_validator("schema_", mode="plain")
    def as_enum_schema(cls, value: str) -> SchemaCompleteness:
        return SchemaCompleteness(value.strip())

    @field_validator("extension", mode="plain")
    def as_enum_extension(cls, value: str) -> ExtensionCategory:
        return ExtensionCategory(value.strip())

    @field_validator("data_model_type", mode="plain")
    def as_enum_model_type(cls, value: str) -> DataModelType:
        return DataModelType(value.strip())

    def as_identifier(self) -> str:
        return f"{self.prefix}:{self.name}"

    def get_prefix(self) -> str:
        return self.prefix


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
        parent: The parent class of the class.
        reference: Reference of the source of the information for given resource
        match_type: The match type of the resource being described and the source entity.
    """

    class_: ClassEntityType = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    parent: ClassEntityList | None = Field(alias="Parent Class", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    comment: str | None = Field(alias="Comment", default=None)

    def _identifier(self) -> tuple[Hashable, ...]:
        return (self.class_,)

    @field_serializer("reference", when_used="always")
    def set_reference(self, value: Any, info: SerializationInfo) -> str | None:
        if isinstance(info.context, dict) and info.context.get("as_reference") is True:
            return self.class_.dump()
        return str(value) if value is not None else None

    @field_serializer("class_", when_used="unless-none")
    def remove_default_prefix(self, value: Any, info: SerializationInfo) -> str:
        if (metadata := _get_metadata(info.context)) and isinstance(value, Entity):
            return value.dump(prefix=metadata.prefix, version=metadata.version)
        return str(value)

    @field_serializer("parent", when_used="unless-none")
    def remove_default_prefixes(self, value: Any, info: SerializationInfo) -> str:
        if isinstance(value, list) and (metadata := _get_metadata(info.context)):
            return ",".join(
                parent.dump(prefix=metadata.prefix, version=metadata.version)
                if isinstance(parent, Entity)
                else str(parent)
                for parent in value
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
        reference: Reference to the source of the information, HTTP URI
        match_type: The match type of the resource being described and the source entity.
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
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    transformation: RDFPath | None = Field(alias="Transformation", default=None)
    comment: str | None = Field(alias="Comment", default=None)
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

    @field_serializer("reference", when_used="always")
    def set_reference(self, value: Any, info: SerializationInfo) -> str | None:
        # When rules as dumped as reference, we set the reference to the class
        if isinstance(info.context, dict) and info.context.get("as_reference") is True:
            return str(
                ReferenceEntity(
                    prefix=str(self.class_.prefix),
                    suffix=self.class_.suffix,
                    property=self.property_,
                )
            )
        return str(value) if value is not None else None

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
    last: "InformationRules | None" = Field(None, alias="Last")
    reference: "InformationRules | None" = Field(None, alias="Reference")

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

        # update parent classes
        for class_ in self.classes:
            if class_.parent:
                for parent in class_.parent:
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
            "external_id": self.metadata.prefix,
            "version": self.metadata.version,
            "classes": len(self.classes),
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
