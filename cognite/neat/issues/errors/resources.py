from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from cognite.neat.issues import NeatError
from cognite.neat.utils.text import humanize_sequence

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
class DuplicatedResourceError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} is duplicated in {location}"""

    fix = "Remove the duplicate {resource_type} {identifier}."
    location: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=repr(self.identifier), location=self.location
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["location"] = self.location
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
    """The {resource_type} with identifier {identifier} referred by
    {referred_type} {referred_by} does not exist"""

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
class DuplicatedMappingError(ResourceError[T_Identifier], Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} is mapped to by: {mappings}. Ensure
    that there is only one mapping"""

    mappings: frozenset[T_ReferenceIdentifier]

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=repr(self.identifier),
            mappings=humanize_sequence([repr(m) for m in self.mappings]),
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["mappings"] = list(self.mappings)
        return output


@dataclass(frozen=True)
class ResourceNotDefinedError(ResourceError[T_Identifier]):
    """The {resource_type} {identifier} is not defined."""

    extra = "{column_name} {row_number} in {sheet_name}"
    fix = "Define the {resource_type} {identifier} in {location}."

    location: str
    column_name: str | None = None
    row_number: int | None = None
    sheet_name: str | None = None

    def message(self) -> str:
        msg = (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=repr(self.identifier), location=self.location
        )
        if self.column_name and self.row_number and self.sheet_name:
            msg += self.extra.format(
                column_name=self.column_name, row_number=self.row_number, sheet_name=self.sheet_name
            )
        return msg

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["location"] = self.location
        output["column_name"] = self.column_name
        output["row_number"] = self.row_number
        output["sheet_name"] = self.sheet_name
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
class InvalidResourceError(NeatError, Generic[T_Identifier]):
    """The {resource_type} with identifier {identifier} is invalid: {reason}"""

    fix = "Check the error message and correct the instance."

    resource_type: str
    identifier: T_Identifier
    reason: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=repr(self.identifier), reason=self.reason
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
    with values {property_values} in {location_name} {locations}
    """

    property_name: str
    property_values: frozenset[str | int | float | bool | None | tuple[str | int | float | bool | None, ...]]
    locations: tuple[str | int, ...]
    location_name: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=self.identifier,
            property_name=self.property_name,
            property_values=self.property_values,
            locations=self.locations,
            location_name=self.location_name,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property_name"] = self.property_name
        output["property_values"] = list(self.property_values)
        output["locations"] = list(self.locations)
        output["location_name"] = self.location_name
        return output


@dataclass(frozen=True)
class ChangedResourceError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has changed{changed}"""

    changed_properties: frozenset[str]
    changed_attributes: frozenset[str]

    def message(self) -> str:
        if self.changed_properties:
            changed = f" properties {humanize_sequence(list(self.changed_properties))}."
        elif self.changed_attributes:
            changed = f" attributes {humanize_sequence(list(self.changed_attributes))}."
        else:
            changed = "."
        return (
            f"The {self.resource_type} {self.identifier} has changed{changed}"
            f"When extending model with extension set to addition or reshape, the {self.resource_type} "
            "properties must remain the same"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["changed_properties"] = self.changed_properties
        output["changed_attributes"] = self.changed_attributes
        return output
