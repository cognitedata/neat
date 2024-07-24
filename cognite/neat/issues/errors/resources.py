from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from cognite.neat.issues import NeatError

T_Identifier = TypeVar("T_Identifier", bound=Hashable)


@dataclass(frozen=True)
class ResourceError(NeatError, Generic[T_Identifier]):
    """Base class for resource errors"""

    identifier: T_Identifier
    resource_type: str

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        return output


@dataclass(frozen=True)
class ResourceNotFoundError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} is missing: {reason}"""

    fix = "Check the {resource_type} {identifier} and try again."
    reason: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=repr(self.identifier), reason=self.reason
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["reason"] = self.reason
        return output


T_ReferenceIdentifier = TypeVar("T_ReferenceIdentifier", bound=Hashable)


@dataclass(frozen=True)
class ReferredResourceNotFoundError(ResourceError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} referred by {referred_type} {referred_by} does not exist"""

    fix = "Create the {resource_type}"

    referred_by: T_ReferenceIdentifier
    referred_type: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=repr(self.identifier),
            referred_type=self.referred_type,
            referred_by=repr(self.referred_by),
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["referred_by"] = self.referred_by
        output["referred_type"] = self.referred_type
        return output


@dataclass(frozen=True)
class FailedConvertError(NeatError):
    description = "Failed to convert the {identifier} to {target_format}: {reason}"
    fix = "Check the error message and correct the rules."
    identifier: str
    target_format: str
    reason: str

    def message(self) -> str:
        return self.description.format(identifier=self.identifier, target_format=self.target_format, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["identifier"] = self.identifier
        output["targetFormat"] = self.target_format
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class InvalidResourceError(NeatError):
    """The {resource_type} with identifier {identifier} is invalid and will be skipped. {reason}"""

    fix = "Check the error message and correct the instance."

    resource_type: str
    identifier: str
    reason: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=self.identifier, reason=self.reason
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["type"] = self.resource_type
        output["identifier"] = self.identifier
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class MissingIdentifierError(NeatError):
    """The {resource_type} with name {name} is missing an identifier."""

    resource_type: str
    name: str | None = None

    def message(self) -> str:
        return (self.__doc__ or "").format(resource_type=self.resource_type, name=self.name or "unknown")

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["type"] = self.resource_type
        output["name"] = self.name
        return output


@dataclass(frozen=True)
class MultiplePropertyDefinitionsError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has multiple definitions for the property {property_name}
    with values {property_values} in locations {locations}
    """

    property_name: str
    property_values: frozenset[str | int | float | bool | None]
    locations: tuple[str | int, ...]

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=self.identifier,
            property_name=self.property_name,
            property_values=self.property_values,
            locations=self.locations,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property_name"] = self.property_name
        output["property_values"] = list(self.property_values)
        output["locations"] = list(self.locations)
        return output
