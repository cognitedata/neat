import re
from collections.abc import Callable
from typing import Annotated, Any, cast

import rdflib
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
from pydantic_core import PydanticCustomError

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

__all__ = [
    "StrOrListType",
    "StrListType",
    "NamespaceType",
    "PrefixType",
    "ExternalIdType",
    "VersionType",
    "ParentClassType",
    "ClassType",
    "PropertyType",
    "ValueTypeType",
]


def _custom_error(exc_factory: Callable[[str | None, Exception], Any]) -> Any:
    def _validator(value: Any, next_: Any, ctx: ValidationInfo) -> Any:
        try:
            return next_(value, ctx)
        except Exception:
            raise exc_factory(ctx.field_name, value) from None

    return WrapValidator(_validator)


def _raise(exception: PydanticCustomError):
    raise exception


def _split_parent(value: str) -> list[ParentClass] | None:
    if not (isinstance(value, str) and value):
        return None

    parents = []
    for v in value.replace(", ", ",").split(","):
        if ENTITY_ID_REGEX_COMPILED.match(v) or VERSIONED_ENTITY_REGEX_COMPILED.match(v):
            parents.append(ParentClass.from_string(entity_string=v))
        else:
            # if all fails defaults "neat" object which ends up being updated to proper
            # prefix and version upon completion of Rules validation
            parents.append(ParentClass(prefix="undefined", suffix=v, name=v))

    return parents


def _check_parent(value: list[ParentClass]) -> list[ParentClass]:
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


StrOrListType = Annotated[
    str | list[str],
    BeforeValidator(lambda value: value.replace(", ", ",").split(",") if isinstance(value, str) and value else value),
]


StrListType = Annotated[
    list[str],
    BeforeValidator(lambda value: [entry.strip() for entry in value.split(",")] if isinstance(value, str) else value),
]

NamespaceType = Annotated[
    rdflib.Namespace,
    BeforeValidator(
        lambda value: (
            rdflib.Namespace(TypeAdapter(HttpUrl).validate_python(value))
            if value.endswith("#") or value.endswith("/")
            else rdflib.Namespace(TypeAdapter(HttpUrl).validate_python(f"{value}/"))
        )
    ),
]

PrefixType = Annotated[
    str,
    StringConstraints(pattern=prefix_compliance_regex),
    _custom_error(
        lambda _, value: exceptions.PrefixesRegexViolation(
            cast(list[str], [value]), prefix_compliance_regex
        ).to_pydantic_custom_error()
    ),
]

ExternalIdType = Annotated[
    str,
    Field(min_length=1, max_length=255),
]

VersionType = Annotated[
    str,
    StringConstraints(pattern=version_compliance_regex),
    _custom_error(
        lambda _, value: exceptions.VersionRegexViolation(
            version=cast(str, value), regex_expression=version_compliance_regex
        ).to_pydantic_custom_error()
    ),
]


ParentClassType = Annotated[
    list[ParentClass] | None,
    BeforeValidator(_split_parent),
    AfterValidator(_check_parent),
]

ClassType = Annotated[
    str,
    AfterValidator(
        lambda value: (
            _raise(exceptions.MoreThanOneNonAlphanumericCharacter("class_", value).to_pydantic_custom_error())
            if re.search(more_than_one_none_alphanumerics_regex, value)
            else (
                value
                if re.match(class_id_compliance_regex, value)
                else _raise(
                    exceptions.ClassSheetClassIDRegexViolation(
                        value, class_id_compliance_regex
                    ).to_pydantic_custom_error()
                )
            )
        )
    ),
]


PropertyType = Annotated[
    str,
    AfterValidator(
        lambda value: (
            _raise(exceptions.MoreThanOneNonAlphanumericCharacter("property", value).to_pydantic_custom_error())
            if re.search(more_than_one_none_alphanumerics_regex, value)
            else (
                value
                if re.match(property_id_compliance_regex, value)
                else _raise(
                    exceptions.PropertyIDRegexViolation(value, property_id_compliance_regex).to_pydantic_custom_error()
                )
            )
        )
    ),
]

ValueTypeType = Annotated[
    ValueType,
    BeforeValidator(
        lambda value: (
            XSD_VALUE_TYPE_MAPPINGS[value]
            if value in XSD_VALUE_TYPE_MAPPINGS
            else (
                ValueType.from_string(entity_string=value, type_=EntityTypes.object_value_type, mapping=None)
                if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value)
                else ValueType(
                    prefix="undefined", suffix=value, name=value, type_=EntityTypes.object_value_type, mapping=None
                )
            )
        )
    ),
]


SourceType = Annotated[
    rdflib.URIRef | None,
    BeforeValidator(
        lambda value: (
            value
            if not value or (value and isinstance(value, rdflib.URIRef))
            else rdflib.URIRef(str(TypeAdapter(HttpUrl).validate_python(value)))
        ),
    ),
]
