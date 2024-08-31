import warnings
from collections.abc import Callable
from typing import Annotated, Any

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
from cognite.neat.utils.regex_patterns import (
    PATTERNS,
    PREFIX_COMPLIANCE_REGEX,
    PROPERTY_ID_COMPLIANCE_REGEX,
    VERSION_COMPLIANCE_REGEX,
)


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


def _property_validation(value: str) -> str:
    if not PATTERNS.property_id_compliance.match(value):
        raise RegexViolationError(value, PROPERTY_ID_COMPLIANCE_REGEX)
    if PATTERNS.more_than_one_alphanumeric.search(value):
        warnings.warn(
            RegexViolationWarning(value, PROPERTY_ID_COMPLIANCE_REGEX, "property", "MoreThanOneNonAlphanumeric"),
            stacklevel=2,
        )
    return value


PropertyType = Annotated[str, AfterValidator(_property_validation)]
