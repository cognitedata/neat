from dataclasses import dataclass
from typing import Any, Generic

from cognite.neat.issues._base import NeatWarning
from cognite.neat.utils.text import humanize_sequence

from .resources import ResourceWarning, T_Identifier, T_ReferenceIdentifier


@dataclass(frozen=True)
class PropertyTypeNotSupportedWarning(ResourceWarning[T_Identifier]):
    """The {resource_type} with identifier {identifier} has a property {property_name}
    of unsupported type {property_type}. This will be ignored."""

    property_name: str
    property_type: str

    def message(self) -> str:
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
class ReferredPropertyNotFoundWarning(ResourceWarning, Generic[T_Identifier, T_ReferenceIdentifier]):
    """The {resource_type} with identifier {identifier} does not have a property {property_name} referred
    to by {referred_type} {referred_by} does not exist. This will be ignored.
    """

    fix = "Ensure the {resource_type} {identifier} has a {property_name} property"

    referred_by: T_ReferenceIdentifier
    referred_type: str
    property_name: str

    def message(self) -> str:
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
class DuplicatedPropertyDefinitionWarning(NeatWarning):
    """Duplicated {name} for property {property_id}. Got multiple values: {values}.
    {default_action}"""

    extra = "Recommended action: {recommended_action}"

    property_id: str
    name: str
    values: frozenset[str]
    default_action: str
    recommended_action: str | None = None

    def message(self) -> str:
        msg = (self.__doc__ or "").format(
            property_id=self.property_id,
            name=self.name,
            values=humanize_sequence(list(self.values)),
            default_action=self.default_action,
        )
        if self.recommended_action:
            msg += f"\n{self.extra.format(recommended_action=self.recommended_action)}"
        return msg

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["property_id"] = self.property_id
        output["name"] = self.name
        output["values"] = self.values
        output["default_action"] = self.default_action
        return output
