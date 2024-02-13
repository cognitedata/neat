import re
from typing import ClassVar

from pydantic import Field, field_validator

from cognite.neat.rules import exceptions
from cognite.neat.rules.models._base import (
    ENTITY_ID_REGEX_COMPILED,
    VERSIONED_ENTITY_REGEX_COMPILED,
    EntityTypes,
    ParentClass,
)
from cognite.neat.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS, ValueType

from .base import (
    BaseMetadata,
    ExternalId,
    RoleTypes,
    RuleModel,
    SheetEntity,
    SheetList,
    class_id_compliance_regex,
    more_than_one_none_alphanumerics_regex,
    property_id_compliance_regex,
)


class DomainMetadata(BaseMetadata):
    role: ClassVar[RoleTypes] = RoleTypes.domain_expert
    creator: str | list[str]

    @field_validator("creator", mode="before")
    def creator_to_list_if_comma(cls, value):
        if isinstance(value, str) and value:
            return value.replace(", ", ",").split(",")
        return value


class DomainProperty(SheetEntity):
    class_: ExternalId = Field(alias="Class", min_length=1, max_length=255)
    property: ExternalId = Field(alias="Property", min_length=1, max_length=255)
    value_type: ValueType = Field(alias="Value Type")
    min_count: int | None = Field(alias="Min Count", default=None)
    max_count: int | float | None = Field(alias="Max Count", default=None)

    @field_validator("value_type", mode="before")
    def expected_value_type_string_to_entity(cls, value):
        # handle simple types
        if value in XSD_VALUE_TYPE_MAPPINGS.keys():
            return XSD_VALUE_TYPE_MAPPINGS[value]

        # complex types correspond to relations to other classes
        if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):
            return ValueType.from_string(entity_string=value, type_=EntityTypes.object_value_type, mapping=None)
        else:
            return ValueType(
                prefix="undefined", suffix=value, name=value, type_=EntityTypes.object_value_type, mapping=None
            )

    @field_validator("class_", mode="after")
    def is_class_id_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("class_id", value).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value):
            raise exceptions.PropertiesSheetClassIDRegexViolation(
                value, class_id_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @field_validator("property", mode="after")
    def is_property_id_compliant(cls, value, values):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("property_id", value).to_pydantic_custom_error()
        if not re.match(property_id_compliance_regex, value):
            raise exceptions.PropertyIDRegexViolation(value, property_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value


class DomainClass(SheetEntity):
    class_: str = Field(alias="Class")
    description: str | None = Field(None, alias="Description")
    parent: list[ParentClass] | None = Field(alias="Parent Class", default=None)

    @field_validator("parent", mode="before")
    def parent_class_to_list_of_entities(cls, value, values):
        if isinstance(value, str) and value:
            parents = []
            for v in value.replace(", ", ",").split(","):
                if ENTITY_ID_REGEX_COMPILED.match(v) or VERSIONED_ENTITY_REGEX_COMPILED.match(v):
                    parents.append(ParentClass.from_string(entity_string=v))
                else:
                    # if all fails defaults "neat" object which ends up being updated to proper
                    # prefix and version upon completion of Rules validation
                    parents.append(ParentClass(prefix="undefined", suffix=v, name=v))

            return parents
        else:
            return None

    @field_validator("class_", mode="after")
    def is_class_id_compliant(cls, value):
        if re.search(more_than_one_none_alphanumerics_regex, value):
            raise exceptions.MoreThanOneNonAlphanumericCharacter("class_id", value).to_pydantic_custom_error()
        if not re.match(class_id_compliance_regex, value):
            raise exceptions.PropertiesSheetClassIDRegexViolation(
                value, class_id_compliance_regex
            ).to_pydantic_custom_error()
        else:
            return value

    @field_validator("parent", mode="after")
    def is_parent_class_id_compliant(cls, value):
        if isinstance(value, list):
            if illegal_ids := [v for v in value if re.search(more_than_one_none_alphanumerics_regex, v.suffix)]:
                raise exceptions.MoreThanOneNonAlphanumericCharacter(
                    "parent", ", ".join(illegal_ids)
                ).to_pydantic_custom_error()
            if illegal_ids := [v for v in value if not re.match(class_id_compliance_regex, v.suffix)]:
                for v in illegal_ids:
                    print(v.id)
                raise exceptions.ClassSheetParentClassIDRegexViolation(
                    illegal_ids, class_id_compliance_regex
                ).to_pydantic_custom_error()
        return value


class DomainRules(RuleModel):
    metadata: DomainMetadata = Field(alias="Metadata")
    properties: SheetList[DomainProperty] = Field(alias="Properties")
    classes: SheetList[DomainClass] | None = Field(None, alias="Classes")
