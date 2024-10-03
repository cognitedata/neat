import warnings
from collections.abc import Callable
from typing import Annotated, Any, TypeAlias, TypeVar

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

from cognite.neat.issues.errors import RegexViolationError
from cognite.neat.issues.warnings import RegexViolationWarning
from cognite.neat.rules._constants import (
    PATTERNS,
    PREFIX_COMPLIANCE_REGEX,
    VERSION_COMPLIANCE_REGEX,
    EntityTypes,
)
from cognite.neat.rules.models.entities._single_value import (
    ClassEntity,
    ContainerEntity,
    ViewEntity,
)

Entities: TypeAlias = ClassEntity | ViewEntity | ContainerEntity
T_Entities = TypeVar("T_Entities", bound=Entities)


def _custom_error(exc_factory: Callable[[str | None, Exception], Any]) -> Any:
    def _validator(value: Any, next_: Any, ctx: ValidationInfo) -> Any:
        try:
            return next_(value, ctx)
        except Exception:
            raise exc_factory(ctx.field_name, value) from None

    return WrapValidator(_validator)


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
    _custom_error(lambda _, value: RegexViolationError(value, PREFIX_COMPLIANCE_REGEX)),
]

ExternalIdType = Annotated[
    str,
    Field(min_length=1, max_length=255),
]

VersionType = Annotated[
    str,
    StringConstraints(pattern=VERSION_COMPLIANCE_REGEX),
    _custom_error(lambda _, value: RegexViolationError(value, VERSION_COMPLIANCE_REGEX)),
]


def _property_validation(value: str, property_type: EntityTypes) -> str:
    compiled_regex = PATTERNS.entity_pattern(property_type)
    if not compiled_regex.match(value):
        raise RegexViolationError(value, compiled_regex.pattern)
    if PATTERNS.more_than_one_alphanumeric.search(value):
        warnings.warn(
            RegexViolationWarning(
                value,
                compiled_regex.pattern,
                "property",
                "MoreThanOneNonAlphanumeric",
            ),
            stacklevel=2,
        )
    return value


def _property_validation_factory(
    property_type: EntityTypes,
) -> Callable[[str], str]:
    return lambda value: _property_validation(value, property_type)


InformationPropertyType = Annotated[
    str,
    AfterValidator(_property_validation_factory(EntityTypes.information_property)),
]
DmsPropertyType = Annotated[
    str,
    AfterValidator(_property_validation_factory(EntityTypes.dms_property)),
]


def _entity_validation(value: Entities) -> Entities:
    compiled_regex = PATTERNS.entity_pattern(value.type_)
    if not compiled_regex.match(value.suffix):
        raise RegexViolationError(str(value), compiled_regex.pattern)
    return value
