from dataclasses import dataclass
from typing import Generic

from cognite.neat._issues._base import NeatError, ResourceType, T_Identifier, T_ReferenceIdentifier
from cognite.neat._utils.text import humanize_collection


@dataclass(unsafe_hash=True)
class ResourceError(NeatError, Generic[T_Identifier], RuntimeError):
    """Base class for resource errors {resource_type} with identifier {identifier}"""

    identifier: T_Identifier
    resource_type: ResourceType


@dataclass(unsafe_hash=True)
class ResourceDuplicatedError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} is duplicated in {location}"""

    fix = "Remove the duplicate {resource_type} {identifier}."
    location: str


@dataclass(unsafe_hash=True)
class ResourceRetrievalError(ResourceError[T_Identifier]):
    """Failed to retrieve {resource_type} with identifier {identifier}. The error was: {error}"""

    error: str


@dataclass(unsafe_hash=True)
class ResourceNotFoundError(ResourceError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not exist"""

    extra = " This is expected by {referred_type} {referred_by}."

    fix = "Create the {resource_type} {identifier}"

    referred_by: T_ReferenceIdentifier | None = None
    referred_type: ResourceType | None = None
    more: str | None = None

    def as_message(self, include_type: bool = True) -> str:
        msg = (self.__doc__ or "").format(resource_type=self.resource_type, identifier=self.identifier)
        if self.referred_by and self.referred_type:
            msg += self.extra.format(referred_type=self.referred_type, referred_by=self.referred_by)
        if self.more:
            msg += f" {self.more}"
        msg += f" Fix {self.fix.format(resource_type=self.resource_type, identifier=self.identifier)}"
        return msg


@dataclass(unsafe_hash=True)
class ResourceNotDefinedError(ResourceError[T_Identifier]):
    """The {resource_type} {identifier} is not defined in the {location}"""

    extra = "{column_name} {row_number} in {sheet_name}"
    fix = "Define the {resource_type} {identifier} in {location}."

    location: str
    column_name: str | None = None
    row_number: int | None = None
    sheet_name: str | None = None


@dataclass(unsafe_hash=True)
class ResourceConvertionError(ResourceError, ValueError):
    """Failed to convert the {resource_type} {identifier} to {target_format}: {reason}"""

    fix = "Check the error message and correct the rules."
    target_format: str
    reason: str


@dataclass(unsafe_hash=True)
class ResourceCreationError(ResourceError[T_Identifier], ValueError):
    """Failed to create {resource_type} with identifier {identifier}. The error was: {error}"""

    error: str


@dataclass(unsafe_hash=True)
class ResourceMissingIdentifierError(NeatError, ValueError):
    """The {resource_type} with name {name} is missing an identifier."""

    resource_type: ResourceType
    name: str | None = None


@dataclass(unsafe_hash=True)
class ResourceChangedError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has changed{changed}"""

    fix = (
        "When extending model with extension set to addition or reshape, "
        "the {resource_type} properties must remain the same"
    )

    changed_properties: frozenset[str]
    changed_attributes: frozenset[str]

    def as_message(self, include_type: bool = True) -> str:
        if self.changed_properties:
            changed = f" properties {humanize_collection(self.changed_properties)}."
        elif self.changed_attributes:
            changed = f" attributes {humanize_collection(self.changed_attributes)}."
        else:
            changed = "."
        msg = (self.__doc__ or "").format(resource_type=self.resource_type, identifier=self.identifier, changed=changed)
        msg += f"Fix {self.fix.format(resource_type=self.resource_type)}"
        return msg
