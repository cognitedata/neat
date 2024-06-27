import sys
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from pydantic import Field, field_validator, model_validator
from pydantic.main import IncEx
from rdflib import Namespace

from cognite.neat.constants import PREFIXES
from cognite.neat.issues import MultiValueError
from cognite.neat.rules import issues
from cognite.neat.rules.models._base import BaseRules, RoleTypes, SheetList
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.entities import (
    CdfResourceEntityList,
    ClassEntity,
    MultiValueTypeInfo,
    ParentClassEntity,
    Undefined,
)
from cognite.neat.rules.models.information import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
    InformationRules,
)

if TYPE_CHECKING:
    from cognite.neat.rules.models.dms._rules import DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class AssetMetadata(InformationMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.asset_architect


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

    implementation: CdfResourceEntityList | None = Field(alias="Implementation", default=None)


class AssetRules(BaseRules):
    metadata: AssetMetadata = Field(alias="Metadata")
    properties: SheetList[AssetProperty] = Field(alias="Properties")
    classes: SheetList[AssetClass] = Field(alias="Classes")
    prefixes: dict[str, Namespace] = Field(default_factory=lambda: PREFIXES.copy())
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
                for parent in cast(list[ParentClassEntity], class_.parent):
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
            raise MultiValueError([error for error in issue_list if isinstance(error, issues.NeatValidationError)])
        return self

    def dump(
        self,
        mode: Literal["python", "json"] = "python",
        by_alias: bool = False,
        exclude: IncEx = None,
        exclude_none: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        as_reference: bool = False,
    ) -> dict[str, Any]:
        from ._serializer import _AssetRulesSerializer

        dumped = self.model_dump(
            mode=mode,
            by_alias=by_alias,
            exclude=exclude,
            exclude_none=exclude_none,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
        )
        prefix = self.metadata.prefix
        serializer = _AssetRulesSerializer(by_alias, prefix)
        cleaned = serializer.clean(dumped, as_reference)
        last = "Last" if by_alias else "last"
        if last_dump := cleaned.get(last):
            cleaned[last] = serializer.clean(last_dump, False)
        reference = "Reference" if by_alias else "reference"
        if self.reference and (ref_dump := cleaned.get(reference)):
            prefix = self.reference.metadata.prefix
            cleaned[reference] = _AssetRulesSerializer(by_alias, prefix).clean(ref_dump, True)
        return cleaned

    def as_domain_rules(self) -> DomainRules:
        from ._converter import _AssetRulesConverter

        return _AssetRulesConverter(self.as_information_architect_rules()).as_domain_rules()

    def as_dms_architect_rules(self) -> "DMSRules":
        from ._converter import _AssetRulesConverter

        return _AssetRulesConverter(self.as_information_architect_rules()).as_dms_architect_rules()

    def as_information_architect_rules(self) -> InformationRules:
        return InformationRules.model_validate(self.model_dump())
