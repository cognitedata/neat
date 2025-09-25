import warnings
from collections.abc import Callable
from typing import Annotated, Any, TypeAlias, TypeVar

import rdflib
from pydantic import (
    AfterValidator,
    BeforeValidator,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationInfo,
    WrapValidator,
)
from pydantic.functional_serializers import PlainSerializer

from cognite.neat.v0.core._data_model._constants import (
    DATA_MODEL_COMPLIANCE_REGEX,
    PATTERNS,
    PREFIX_COMPLIANCE_REGEX,
    VERSION_COMPLIANCE_REGEX,
    EntityTypes,
)
from cognite.neat.v0.core._data_model.models.entities._multi_value import MultiValueTypeInfo
from cognite.neat.v0.core._data_model.models.entities._single_value import (
    ConceptEntity,
    ContainerEntity,
    ViewEntity,
)
from cognite.neat.v0.core._issues.errors import RegexViolationError
from cognite.neat.v0.core._issues.warnings import RegexViolationWarning

Entities: TypeAlias = ConceptEntity | ViewEntity | ContainerEntity
T_Entities = TypeVar("T_Entities", bound=Entities)


def _custom_error(exc_factory: Callable[[str | None, Exception], Any]) -> Any:
    def _validator(value: Any, next_: Any, ctx: ValidationInfo) -> Any:
        try:
            return next_(value, ctx)
        except ValueError as e:
            if value is None:
                raise e
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

URIRefType = Annotated[
    rdflib.URIRef,
    BeforeValidator(lambda value: rdflib.URIRef(value)),
    PlainSerializer(
        lambda value: str(value),
        return_type=str,
        when_used="unless-none",
    ),
]

PrefixType = Annotated[
    str,
    StringConstraints(pattern=PREFIX_COMPLIANCE_REGEX),
    _custom_error(
        lambda _, value: RegexViolationError(value, PREFIX_COMPLIANCE_REGEX, "prefix entry in metadata"),
    ),
]

DataModelExternalIdType = Annotated[
    str,
    StringConstraints(pattern=DATA_MODEL_COMPLIANCE_REGEX),
    _custom_error(
        lambda _, value: RegexViolationError(value, DATA_MODEL_COMPLIANCE_REGEX, "external ID entry in metadata")
    ),
]


VersionType = Annotated[
    str,
    BeforeValidator(str),
    StringConstraints(pattern=VERSION_COMPLIANCE_REGEX),
    _custom_error(lambda _, value: RegexViolationError(value, VERSION_COMPLIANCE_REGEX, "version entry in metadata")),
]


def _external_id_validation_factory(entity_type: EntityTypes, location: str) -> Callable:
    def _external_id_validation(value: str) -> str:
        compiled_regex = PATTERNS.entity_pattern(entity_type)
        if not compiled_regex.match(value):
            raise RegexViolationError(value, compiled_regex.pattern, location)
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

    return _external_id_validation


SpaceType = Annotated[
    str,
    AfterValidator(_external_id_validation_factory(EntityTypes.space, "")),
]

ConceptualPropertyType = Annotated[
    str,
    AfterValidator(_external_id_validation_factory(EntityTypes.conceptual_property, "Property column in properties")),
]
PhysicalPropertyType = Annotated[
    str,
    AfterValidator(_external_id_validation_factory(EntityTypes.physical_property, "Property column in properties")),
]


def _entity_validation(value: Entities, location: str) -> Entities:
    suffix_regex = PATTERNS.entity_pattern(value.type_)
    if not suffix_regex.match(value.suffix):
        raise RegexViolationError(str(value), suffix_regex.pattern, location)
    return value


ConceptEntityType = Annotated[ConceptEntity, AfterValidator(lambda v: _entity_validation(v, "the Class column"))]
ViewEntityType = Annotated[ViewEntity, AfterValidator(lambda v: _entity_validation(v, "the View column"))]
ContainerEntityType = Annotated[
    ContainerEntity, AfterValidator(lambda v: _entity_validation(v, "the Container column"))
]


def _multi_value_type_validation(value: MultiValueTypeInfo, location: str) -> MultiValueTypeInfo:
    for type_ in value.types:
        if isinstance(type_, ConceptEntity):
            _entity_validation(type_, location)
    return value


MultiValueTypeType = Annotated[
    MultiValueTypeInfo, AfterValidator(lambda v: _multi_value_type_validation(v, "the Value Type column"))
]
