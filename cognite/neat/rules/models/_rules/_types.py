import re
from collections.abc import Callable
from typing import Annotated, Any, cast

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationInfo,
    WrapValidator,
)
from rdflib import Namespace

from cognite.neat.rules import exceptions
from cognite.neat.rules.models._base import (
    ENTITY_ID_REGEX_COMPILED,
    VERSIONED_ENTITY_REGEX_COMPILED,
    EntityTypes,
    ParentClass,
)
from cognite.neat.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS, ValueType

from .base import (
    class_id_compliance_regex,
    more_than_one_none_alphanumerics_regex,
    prefix_compliance_regex,
    property_id_compliance_regex,
    version_compliance_regex,
)


def custom_error(exc_factory: Callable[[str | None, Exception], Exception, Any]) -> Any:
    def _validator(v: Any, next_: Any, ctx: ValidationInfo) -> Any:
        try:
            return next_(v, ctx)
        except Exception as e:
            raise exc_factory(ctx.field_name, e, v) from None

    return WrapValidator(_validator)


def raise_(ex):
    raise ex


StrOrListType = Annotated[
    str | list[str],
    BeforeValidator(lambda v: v.replace(", ", ",").split(",") if isinstance(v, str) and v else v),
]


StrListType = Annotated[
    list[str],
    BeforeValidator(lambda v: [entry.strip() for entry in v.split(",")] if isinstance(v, str) else v),
]

NamespaceType = Annotated[
    Namespace,
    BeforeValidator(
        lambda v: (
            Namespace(TypeAdapter(HttpUrl).validate_python(v))
            if v.endswith("#") or v.endswith("/")
            else Namespace(TypeAdapter(HttpUrl).validate_python(f"{v}/"))
        )
    ),
]

PrefixType = Annotated[
    str,
    StringConstraints(pattern=prefix_compliance_regex),
    custom_error(
        lambda field_name, error, value: exceptions.PrefixesRegexViolation(
            [value], prefix_compliance_regex
        ).to_pydantic_custom_error()
    ),
]

ExternalIdType = Annotated[
    str,
    Field(min_items=1, max_items=255),
]

VersionType = Annotated[
    str,
    StringConstraints(pattern=version_compliance_regex),
    custom_error(
        lambda field_name, error, value: exceptions.VersionRegexViolation(
            value, version_compliance_regex
        ).to_pydantic_custom_error()
    ),
]


def split_parent(value: str) -> list[ParentClass] | None:
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


def check_parent(value: list[ParentClass]) -> list[ParentClass]:
    if not value:
        return value
        if illegal_ids := [v for v in value if re.search(more_than_one_none_alphanumerics_regex, v.suffix)]:
            raise exceptions.MoreThanOneNonAlphanumericCharacter(
                "parent", ", ".join(cast(list[str], illegal_ids))
            ).to_pydantic_custom_error()
        if illegal_ids := [v for v in value if not re.match(class_id_compliance_regex, v.suffix)]:
            for v in illegal_ids:
                print(v.id)
            raise exceptions.ClassSheetParentClassIDRegexViolation(
                cast(list[str], illegal_ids), class_id_compliance_regex
            ).to_pydantic_custom_error()
    return value


ParentClassType = Annotated[
    list[ParentClass] | None,
    BeforeValidator(split_parent),
    AfterValidator(check_parent),
]

ClassType = Annotated[
    str,
    AfterValidator(
        lambda v: (
            raise_(exceptions.MoreThanOneNonAlphanumericCharacter("class_", v).to_pydantic_custom_error())
            if re.search(more_than_one_none_alphanumerics_regex, v)
            else (
                v
                if re.match(class_id_compliance_regex, v)
                else raise_(
                    exceptions.ClassSheetClassIDRegexViolation(v, class_id_compliance_regex).to_pydantic_custom_error()
                )
            )
        )
    ),
]


PropertyType = Annotated[
    str,
    AfterValidator(
        lambda v: (
            raise_(exceptions.MoreThanOneNonAlphanumericCharacter("property", v).to_pydantic_custom_error())
            if re.search(more_than_one_none_alphanumerics_regex, v)
            else (
                v
                if re.match(property_id_compliance_regex, v)
                else raise_(
                    exceptions.PropertyIDRegexViolation(v, property_id_compliance_regex).to_pydantic_custom_error()
                )
            )
        )
    ),
]

ValueTypeType = Annotated[
    ValueType,
    BeforeValidator(
        lambda v: (
            XSD_VALUE_TYPE_MAPPINGS[v]
            if v in XSD_VALUE_TYPE_MAPPINGS
            else (
                ValueType.from_string(entity_string=v, type_=EntityTypes.object_value_type, mapping=None)
                if ENTITY_ID_REGEX_COMPILED.match(v) or VERSIONED_ENTITY_REGEX_COMPILED.match(v)
                else ValueType(prefix="undefined", suffix=v, name=v, type_=EntityTypes.object_value_type, mapping=None)
            )
        )
    ),
]
