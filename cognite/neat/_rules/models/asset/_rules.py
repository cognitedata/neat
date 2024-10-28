import sys
from typing import Any, ClassVar, cast

from pydantic import Field, field_validator, model_validator
from rdflib import Namespace

from cognite.neat._constants import get_default_prefixes
from cognite.neat._rules.models._base_rules import BaseRules, RoleTypes, SheetList
from cognite.neat._rules.models.entities import (
    CdfResourceEntityList,
    ClassEntity,
    MultiValueTypeInfo,
    Undefined,
)
from cognite.neat._rules.models.information import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
    InformationRules,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class AssetMetadata(InformationMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.asset


class AssetClass(InformationClass): ...


class AssetProperty(InformationProperty):
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
        implementation: Details on how given class-property is implemented in the classic CDF
    """

    implementation: CdfResourceEntityList = Field(alias="Implementation")


class AssetRules(BaseRules):
    metadata: AssetMetadata = Field(alias="Metadata")
    properties: SheetList[AssetProperty] = Field(alias="Properties")
    classes: SheetList[AssetClass] = Field(alias="Classes")
    prefixes: dict[str, Namespace] = Field(default_factory=get_default_prefixes)
    last: "AssetRules | None" = Field(None, alias="Last")
    reference: "AssetRules | None" = Field(None, alias="Reference")

    @field_validator("prefixes", mode="before")
    def parse_str(cls, values: Any) -> Any:
        if isinstance(values, dict):
            return {key: Namespace(value) if isinstance(value, str) else value for key, value in values.items()}
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
    def post_validation(self) -> "AssetRules":
        from ._validation import AssetPostValidation

        issue_list = AssetPostValidation(cast(InformationRules, self)).validate()
        if issue_list.warnings:
            issue_list.trigger_warnings()
        if issue_list.has_errors:
            raise issue_list.as_exception()
        return self
