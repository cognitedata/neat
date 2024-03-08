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
from pydantic.functional_serializers import PlainSerializer
from pydantic_core import PydanticCustomError

from cognite.neat.rules import exceptions

from ._base import (
    CLASS_ID_COMPLIANCE_REGEX,
    ENTITY_ID_REGEX_COMPILED,
    MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX,
    PREFIX_COMPLIANCE_REGEX,
    PROPERTY_ID_COMPLIANCE_REGEX,
    VERSION_COMPLIANCE_REGEX,
    VERSIONED_ENTITY_REGEX_COMPILED,
    ClassEntity,
    ContainerEntity,
    ParentClassEntity,
    Undefined,
    ViewEntity,
)
from ._value import DMS_VALUE_TYPE_MAPPINGS, XSD_VALUE_TYPE_MAPPINGS, DMSValueType, XSDValueType


def _custom_error(exc_factory: Callable[[str | None, Exception], Any]) -> Any:
    def _validator(value: Any, next_: Any, ctx: ValidationInfo) -> Any:
        try:
            return next_(value, ctx)
        except Exception:
            raise exc_factory(ctx.field_name, value) from None

    return WrapValidator(_validator)


def _raise(exception: PydanticCustomError):
    raise exception


def _split_parent(value: str | list[ParentClassEntity]) -> list[ParentClassEntity] | None:
    if isinstance(value, list) and all(isinstance(x, ParentClassEntity) for x in value):
        return value

    if not (isinstance(value, str) and value):
        return None

    parents = []
    for v in value.replace(", ", ",").split(","):
        if ENTITY_ID_REGEX_COMPILED.match(v) or VERSIONED_ENTITY_REGEX_COMPILED.match(v):
            parents.append(ParentClassEntity.from_string(entity_string=v))
        else:
            parents.append(ParentClassEntity(prefix=Undefined, suffix=v, name=v))

    return parents


def _check_parent(value: list[ParentClassEntity]) -> list[ParentClassEntity]:
    if not value:
        return value
    if illegal_ids := [v for v in value if re.search(MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX, v.suffix)]:
        raise exceptions.MoreThanOneNonAlphanumericCharacter(
            "parent", ", ".join(cast(list[str], illegal_ids))
        ).to_pydantic_custom_error()
    if illegal_ids := [v for v in value if not re.match(CLASS_ID_COMPLIANCE_REGEX, v.suffix)]:
        for v in illegal_ids:
            print(v.id)
        raise exceptions.ClassSheetParentClassIDRegexViolation(
            cast(list[str], illegal_ids), CLASS_ID_COMPLIANCE_REGEX
        ).to_pydantic_custom_error()
    return value


StrOrListType = Annotated[
    str | list[str],
    BeforeValidator(lambda value: value.replace(", ", ",").split(",") if isinstance(value, str) and value else value),
    PlainSerializer(
        lambda value: ",".join([entry for entry in value if entry]) if isinstance(value, list) else value,
        return_type=str,
        when_used="unless-none",
    ),
]


StrListType = Annotated[
    list[str],
    BeforeValidator(lambda value: [entry.strip() for entry in value.split(",")] if isinstance(value, str) else value),
    PlainSerializer(
        lambda value: ",".join([entry for entry in value if entry]), return_type=str, when_used="unless-none"
    ),
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
    StringConstraints(pattern=PREFIX_COMPLIANCE_REGEX),
    _custom_error(
        lambda _, value: exceptions.PrefixesRegexViolation(
            cast(list[str], [value]), PREFIX_COMPLIANCE_REGEX
        ).to_pydantic_custom_error()
    ),
]

ExternalIdType = Annotated[
    str,
    Field(min_length=1, max_length=255),
]

VersionType = Annotated[
    str,
    StringConstraints(pattern=VERSION_COMPLIANCE_REGEX),
    _custom_error(
        lambda _, value: exceptions.VersionRegexViolation(
            version=cast(str, value), regex_expression=VERSION_COMPLIANCE_REGEX
        ).to_pydantic_custom_error()
    ),
]


ParentClassType = Annotated[
    list[ParentClassEntity] | None,
    BeforeValidator(_split_parent),
    AfterValidator(_check_parent),
    PlainSerializer(
        lambda v: ",".join([entry.versioned_id for entry in v]) if v else None,
        return_type=str,
        when_used="unless-none",
    ),
]

ClassType = Annotated[
    ClassEntity,
    BeforeValidator(lambda value: (ClassType.from_raw(value) if isinstance(value, str) else value)),
    AfterValidator(
        lambda value: (
            _raise(exceptions.MoreThanOneNonAlphanumericCharacter("class_", value.suffix).to_pydantic_custom_error())
            if re.search(MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX, value.suffix)
            else (
                value
                if re.match(CLASS_ID_COMPLIANCE_REGEX, value.suffix)
                else _raise(
                    exceptions.ClassSheetClassIDRegexViolation(
                        value.suffix, CLASS_ID_COMPLIANCE_REGEX
                    ).to_pydantic_custom_error()
                )
            )
        )
    ),
    PlainSerializer(
        lambda v: v.versioned_id,
        return_type=str,
        when_used="unless-none",
    ),
]


PropertyType = Annotated[
    str,
    AfterValidator(
        lambda value: (
            _raise(exceptions.MoreThanOneNonAlphanumericCharacter("property", value).to_pydantic_custom_error())
            if re.search(MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX, value)
            else (
                value
                if re.match(PROPERTY_ID_COMPLIANCE_REGEX, value)
                else _raise(
                    exceptions.PropertyIDRegexViolation(value, PROPERTY_ID_COMPLIANCE_REGEX).to_pydantic_custom_error()
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


ContainerType = Annotated[
    ContainerEntity,
    BeforeValidator(ContainerEntity.from_raw),
    PlainSerializer(
        lambda v: v.versioned_id,
        return_type=str,
        when_used="unless-none",
    ),
]


ViewType = Annotated[
    ViewEntity,
    BeforeValidator(ViewEntity.from_raw),
    PlainSerializer(
        lambda v: v.versioned_id,
        return_type=str,
        when_used="unless-none",
    ),
]


def _semantic_value_type_before_validator(value: Any) -> Any:
    if isinstance(value, XSDValueType | ClassEntity) or not isinstance(value, str):
        return value
    elif value in XSD_VALUE_TYPE_MAPPINGS:
        return XSD_VALUE_TYPE_MAPPINGS[value]
    else:
        return ClassEntity.from_raw(value)


SemanticValueType = Annotated[
    XSDValueType | ClassEntity,
    BeforeValidator(_semantic_value_type_before_validator),
    PlainSerializer(
        lambda v: v.versioned_id,
        return_type=str,
        when_used="unless-none",
    ),
]

CdfValueType = Annotated[
    DMSValueType | ViewEntity,
    BeforeValidator(
        lambda value: DMS_VALUE_TYPE_MAPPINGS[value] if value in DMS_VALUE_TYPE_MAPPINGS else ViewEntity.from_raw(value)
    ),
    PlainSerializer(
        lambda v: v.versioned_id if isinstance(v, ViewEntity) else v.dms()._type,
        return_type=str,
        when_used="unless-none",
    ),
]


def _from_str_or_list_container(value: Any) -> list[ContainerEntity] | Any:
    if not value:
        return value
    if isinstance(value, str):
        return [ContainerEntity.from_raw(entry.strip()) for entry in value.split(",")]
    elif isinstance(value, list):
        return [ContainerEntity.from_raw(entry.strip()) if isinstance(entry, str) else entry for entry in value]
    else:
        return value


def _from_str_or_list_view(value: Any) -> list[ViewEntity] | Any:
    if not value:
        return value
    if isinstance(value, str):
        return [ViewEntity.from_raw(entry.strip()) for entry in value.split(",")]
    elif isinstance(value, list):
        return [ViewEntity.from_raw(entry.strip()) if isinstance(entry, str) else entry for entry in value]
    else:
        return value


ContainerListType = Annotated[
    list[ContainerEntity],
    BeforeValidator(_from_str_or_list_container),
    PlainSerializer(
        lambda v: ",".join([entry.versioned_id for entry in v]),
        return_type=str,
        when_used="unless-none",
    ),
]

ViewListType = Annotated[
    list[ViewEntity],
    BeforeValidator(_from_str_or_list_view),
    PlainSerializer(
        lambda v: ",".join([entry.versioned_id for entry in v]),
        return_type=str,
        when_used="unless-none",
    ),
]
