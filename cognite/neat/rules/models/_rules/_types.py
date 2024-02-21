import re
import sys
from collections.abc import Callable
from functools import total_ordering
from typing import Annotated, Any, ClassVar, cast

import rdflib
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from pydantic import (
    AfterValidator,
    BaseModel,
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
from cognite.neat.rules.models._base import (
    ENTITY_ID_REGEX_COMPILED,
    PREFIX_REGEX,
    SUFFIX_REGEX,
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

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

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
    "ViewType",
    "ViewListType",
    "ContainerType",
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

# Sentinel value. This is used to indicate that no prefix is set for an entity.
Undefined = type(object())


# mypy: ignore-errors
@total_ordering
class Entity(BaseModel, arbitrary_types_allowed=True):
    """Entity is a class or property in OWL/RDF sense."""

    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: str | Undefined = Undefined
    suffix: str
    version: str | None = None

    def __lt__(self, other: object) -> bool:
        if type(self) is not type(other) or not isinstance(other, Entity):
            return NotImplemented
        return self.versioned_id < other.versioned_id

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other) or not isinstance(other, Entity):
            return NotImplemented
        return self.versioned_id == other.versioned_id

    def __hash__(self) -> int:
        return hash(self.versioned_id)

    @property
    def id(self) -> str:
        if self.prefix is Undefined:
            return self.suffix
        else:
            return f"{self.prefix}:{self.suffix}"

    @property
    def versioned_id(self) -> str:
        if self.version is None:
            return self.id
        else:
            return f"{self.id}(version={self.version})"

    @property
    def space(self) -> str:
        """Returns entity space in CDF."""
        return self.prefix

    @property
    def external_id(self) -> str:
        """Returns entity external id in CDF."""
        return self.suffix

    def __repr__(self):
        return self.versioned_id

    def __str__(self):
        return self.versioned_id

    @classmethod
    def from_string(cls, entity_string: str, base_prefix: str | None = None) -> Self:
        if result := VERSIONED_ENTITY_REGEX_COMPILED.match(entity_string):
            return cls(
                prefix=result.group("prefix"),
                suffix=result.group("suffix"),
                version=result.group("version"),
            )
        elif result := ENTITY_ID_REGEX_COMPILED.match(entity_string):
            return cls(prefix=result.group("prefix"), suffix=result.group("suffix"))
        elif base_prefix and re.match(SUFFIX_REGEX, entity_string) and re.match(PREFIX_REGEX, base_prefix):
            return cls(prefix=base_prefix, suffix=entity_string)
        else:
            raise ValueError(f"{cls.__name__} is expected to be prefix:suffix, got {entity_string}")

    @classmethod
    def from_list(cls, entity_strings: list[str], base_prefix: str | None = None) -> list[Self]:
        return [
            cls.from_string(entity_string=entity_string, base_prefix=base_prefix) for entity_string in entity_strings
        ]


class ContainerEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.container

    @classmethod
    def from_raw(cls, value: str) -> "ContainerEntity":
        if not value:
            return ContainerEntity(prefix=Undefined, suffix=value)

        if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):
            return ContainerEntity.from_string(entity_string=value)
        else:
            return ContainerEntity(prefix=Undefined, suffix=value)

    def as_id(self, default_space: str) -> ContainerId:
        if self.space is Undefined:
            return ContainerId(space=default_space, external_id=self.external_id)
        else:
            return ContainerId(space=self.space, external_id=self.external_id)


class ViewEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.view

    @classmethod
    def from_raw(cls, value: str) -> "ViewEntity":
        if not value:
            return ViewEntity(prefix=Undefined, suffix=value)

        if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):
            return ViewEntity.from_string(entity_string=value)
        else:
            return ViewEntity(prefix=Undefined, suffix=value)

    def as_id(self, default_space: str, default_version: str) -> ViewId:
        if self.space is Undefined:
            space = default_space
        else:
            space = self.space
        version = self.version or default_version
        return ViewId(space=space, external_id=self.external_id, version=version)


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


def _from_str_or_list(value: Any) -> list[ViewEntity] | Any:
    if not value:
        return value
    if isinstance(value, str):
        return [ViewEntity.from_raw(entry.strip()) for entry in value.split(",")]
    elif isinstance(value, list):
        return [ViewEntity.from_raw(entry.strip()) for entry in value]
    else:
        return value


ViewListType = Annotated[
    list[ViewEntity],
    BeforeValidator(_from_str_or_list),
    PlainSerializer(
        lambda v: ",".join([entry.versioned_id for entry in v]),
        return_type=str,
        when_used="unless-none",
    ),
]
