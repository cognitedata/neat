import math
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic.main import IncEx
from rdflib import Namespace

from cognite.neat.constants import PREFIXES
from cognite.neat.issues import MultiValueError
from cognite.neat.rules import exceptions, issues
from cognite.neat.rules.models._base import (
    BaseMetadata,
    BaseRules,
    DataModelType,
    ExtensionCategory,
    ExtensionCategoryType,
    MatchType,
    RoleTypes,
    SchemaCompleteness,
    SheetEntity,
    SheetList,
)
from cognite.neat.rules.models._rdfpath import (
    RDFPath,
    TransformationRuleType,
    parse_rule,
)
from cognite.neat.rules.models._types import (
    NamespaceType,
    PrefixType,
    PropertyType,
    StrListType,
    VersionType,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.entities import (
    ClassEntity,
    EntityTypes,
    MultiValueTypeInfo,
    ParentClassEntity,
    ParentEntityList,
    ReferenceEntity,
    Undefined,
    UnknownEntity,
    URLEntity,
)

if TYPE_CHECKING:
    from cognite.neat.rules.models import AssetRules, DMSRules


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.information_architect
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
        return SchemaCompleteness(value)

    @field_validator("extension", mode="plain")
    def as_enum_extension(cls, value: str) -> ExtensionCategory:
        return ExtensionCategory(value)

    @field_validator("data_model_type", mode="plain")
    def as_enum_model_type(cls, value: str) -> DataModelType:
        return DataModelType(value)

    def as_identifier(self) -> str:
        return f"{self.prefix}:{self.name}"


class InformationClass(SheetEntity):
    """
    Class is a category of things that share a common set of attributes and relationships.

    Args:
        class_: The class ID of the class.
        description: A description of the class.
        parent: The parent class of the class.
        reference: Reference of the source of the information for given resource
        match_type: The match type of the resource being described and the source entity.
    """

    class_: ClassEntity = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    parent: ParentEntityList | None = Field(alias="Parent Class", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    comment: str | None = Field(alias="Comment", default=None)


class InformationProperty(SheetEntity):
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

    class_: ClassEntity = Field(alias="Class")
    property_: PropertyType = Field(alias="Property")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)
    value_type: DataType | ClassEntity | MultiValueTypeInfo | UnknownEntity = Field(
        alias="Value Type", union_mode="left_to_right"
    )
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)
    default: Any | None = Field(alias="Default", default=None)
    reference: URLEntity | ReferenceEntity | None = Field(alias="Reference", default=None, union_mode="left_to_right")
    match_type: MatchType | None = Field(alias="Match Type", default=None)
    transformation: str | RDFPath | None = Field(alias="Transformation", default=None)
    comment: str | None = Field(alias="Comment", default=None)
    inherited: bool = Field(
        default=False,
        alias="Inherited",
        description="Flag to indicate if the property is inherited, only use for internal purposes",
    )

    @field_serializer("max_count", when_used="json-unless-none")
    def serialize_max_count(self, value: int | float | None) -> int | float | None | str:
        if isinstance(value, float) and math.isinf(value):
            return None
        return value

    @field_validator("max_count", mode="before")
    def parse_max_count(cls, value: int | float | None) -> int | float | None:
        if value is None:
            return float("inf")
        return value

    @model_validator(mode="after")
    def generate_valid_transformation(self):
        # TODO: Currently only supporting RDFpath
        if self.transformation:
            self.transformation = parse_rule(self.transformation, TransformationRuleType.rdfpath)
        return self

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

            if type(default_value) != self.value_type.python:
                try:
                    if isinstance(self.default, list):
                        updated_list = []
                        for value in self.default:
                            updated_list.append(self.value_type.python(value))
                        self.default = updated_list
                    else:
                        self.default = self.value_type.python(self.default)

                except Exception:
                    exceptions.DefaultValueTypeNotProper(
                        self.property_,
                        type(self.default),
                        self.value_type.python,
                    )
        return self

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


class InformationRules(BaseRules):
    metadata: InformationMetadata = Field(alias="Metadata")
    properties: SheetList[InformationProperty] = Field(alias="Properties")
    classes: SheetList[InformationClass] = Field(alias="Classes")
    prefixes: dict[str, Namespace] = Field(default_factory=lambda: PREFIXES.copy(), alias="Prefixes")
    last: "InformationRules | None" = Field(None, alias="Last")
    reference: "InformationRules | None" = Field(None, alias="Reference")

    @field_validator("prefixes", mode="before")
    def parse_str(cls, values: Any) -> Any:
        if isinstance(values, dict):
            return {key: Namespace(value) if isinstance(value, str) else value for key, value in values.items()}
        elif values is None:
            values = PREFIXES.copy()
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
    def post_validation(self) -> "InformationRules":
        from ._validation import InformationPostValidation

        issue_list = InformationPostValidation(self).validate()
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
        from ._serializer import _InformationRulesSerializer

        dumped = self.model_dump(
            mode=mode,
            by_alias=by_alias,
            exclude=exclude,
            exclude_none=exclude_none,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
        )
        prefix = self.metadata.prefix
        serializer = _InformationRulesSerializer(by_alias, prefix)
        cleaned = serializer.clean(dumped, as_reference)
        last = "Last" if by_alias else "last"
        if last_dump := cleaned.get(last):
            cleaned[last] = serializer.clean(last_dump, False)
        reference = "Reference" if by_alias else "reference"
        if self.reference and (ref_dump := cleaned.get(reference)):
            prefix = self.reference.metadata.prefix
            cleaned[reference] = _InformationRulesSerializer(by_alias, prefix).clean(ref_dump, True)
        return cleaned

    def as_domain_rules(self) -> DomainRules:
        from ._converter import _InformationRulesConverter

        return _InformationRulesConverter(self).as_domain_rules()

    def as_asset_architect_rules(self) -> "AssetRules":
        from ._converter import _InformationRulesConverter

        return _InformationRulesConverter(self).as_asset_architect_rules()

    def as_dms_architect_rules(self) -> "DMSRules":
        from ._converter import _InformationRulesConverter

        return _InformationRulesConverter(self).as_dms_architect_rules()
