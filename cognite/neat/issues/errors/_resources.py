from dataclasses import dataclass
from typing import Generic

from cognite.neat.issues._base import NeatError, ResourceType, T_Identifier, T_ReferenceIdentifier
from cognite.neat.utils.text import humanize_collection


@dataclass(frozen=True)
class ResourceError(NeatError, Generic[T_Identifier], RuntimeError):
    """Base class for resource errors {resource_type} with identifier {identifier}"""

    identifier: T_Identifier
    resource_type: ResourceType


@dataclass(frozen=True)
class DuplicatedResourceError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} is duplicated in {location}"""

    fix = "Remove the duplicate {resource_type} {identifier}."
    location: str


@dataclass(frozen=True)
class ResourceNotFoundError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} is missing: {reason}"""

    fix = "Check the {resource_type} {identifier} and try again."
    reason: str


@dataclass(frozen=True)
class ReferredResourceNotFoundError(ResourceError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} referred by
    {referred_type} {referred_by} does not exist"""

    fix = "Create the {resource_type}"

    referred_by: T_ReferenceIdentifier
    referred_type: ResourceType


@dataclass(frozen=True)
class DuplicatedMappingError(ResourceError[T_Identifier], Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} is mapped to by: {mappings}. Ensure
    that there is only one mapping"""

    mappings: frozenset[T_ReferenceIdentifier]


@dataclass(frozen=True)
class ResourceNotDefinedError(ResourceError[T_Identifier]):
    """The {resource_type} {identifier} is not defined in the {location}"""

    extra = "{column_name} {row_number} in {sheet_name}"
    fix = "Define the {resource_type} {identifier} in {location}."

    location: str
    column_name: str | None = None
    row_number: int | None = None
    sheet_name: str | None = None


@dataclass(frozen=True)
class FailedConvertError(NeatError, ValueError):
    """Failed to convert the {identifier} to {target_format}: {reason}"""

    fix = "Check the error message and correct the rules."
    identifier: str
    target_format: str
    reason: str


@dataclass(frozen=True)
class InvalidResourceError(NeatError, Generic[T_Identifier], ValueError):
    """The {resource_type} with identifier {identifier} is invalid: {reason}"""

    fix = "Check the error message and correct the instance."

    resource_type: ResourceType
    identifier: T_Identifier
    reason: str


@dataclass(frozen=True)
class MissingIdentifierError(NeatError, ValueError):
    """The {resource_type} with name {name} is missing an identifier."""

    resource_type: ResourceType
    name: str | None = None


@dataclass(frozen=True)
class DuplicatedPropertyDefinitionsError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has multiple definitions for the property {property_name}
    with values {property_values} in {location_name} {locations}
    """

    property_name: str
    property_values: frozenset[str | int | float | bool | None | tuple[str | int | float | bool | None, ...]]
    locations: tuple[str | int, ...]
    location_name: str


@dataclass(frozen=True)
class ChangedResourceError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has changed{changed}"""

    fix = (
        "When extending model with extension set to addition or reshape, "
        "the {resource_type} properties must remain the same"
    )

    changed_properties: frozenset[str]
    changed_attributes: frozenset[str]

    def as_message(self) -> str:
        if self.changed_properties:
            changed = f" properties {humanize_collection(self.changed_properties)}."
        elif self.changed_attributes:
            changed = f" attributes {humanize_collection(self.changed_attributes)}."
        else:
            changed = "."
        msg = (self.__doc__ or "").format(resource_type=self.resource_type, identifier=self.identifier, changed=changed)
        msg += f"Fix {self.fix.format(resource_type=self.resource_type)}"
        return msg
