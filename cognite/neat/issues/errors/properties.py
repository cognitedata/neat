from dataclasses import dataclass
from typing import Any, Generic

from .resources import ResourceError, T_Identifier, T_ReferenceIdentifier


@dataclass(frozen=True)
class PropertyNotFoundError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name}"""

    property_name: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=repr(self.identifier), property_name=self.property_name
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property_name"] = self.property_name
        return output


@dataclass(frozen=True)
class ReferredPropertyNotFoundError(ResourceError, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name} referred
    to by {referred_type} {referred_by} does not exist
    """

    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"

    referred_by: T_ReferenceIdentifier
    referred_type: str
    property_name: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=repr(self.identifier),
            referred_type=self.referred_type,
            referred_by=repr(self.referred_by),
            property_name=self.property_name,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["referred_by"] = self.referred_by
        output["referred_type"] = self.referred_type
        output["property_name"] = self.property_name
        return output


@dataclass(frozen=True)
class PropertyTypeNotSupportedError(ResourceError[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}"""

    property_name: str
    property_type: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=repr(self.identifier),
            property_name=self.property_name,
            property_type=self.property_type,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property_name"] = self.property_name
        output["property_type"] = self.property_type
        return output


@dataclass(frozen=True)
class InvalidPropertyDefinitionError(ResourceError[T_Identifier]):
    """Invalid property definition for {resource_type} {identifier}.{property_name}: {reason}"""

    property_name: str
    reason: str

    def as_message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=repr(self.identifier),
            property_name=self.property_name,
            reason=self.reason,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property_name"] = self.property_name
        output["reason"] = self.reason
        return output
