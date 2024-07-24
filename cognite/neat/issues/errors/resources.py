from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class ResourceError(NeatError):
    """Base class for resource errors"""

    identifier: str
    resource_type: str


@dataclass(frozen=True)
class ResourceNotFoundError(ResourceError):
    """The {resource_type} with identifier {identifier} is missing: {reason}"""

    fix = "Check the {resource_type} {identifier} and try again."
    reason: str

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type, identifier=self.identifier, reason=self.reason
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["resource_type"] = self.resource_type
        output["identifier"] = self.identifier
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class ReferredResourceNotFoundError(ResourceError):
    """The {resource_type} with identifier {identifier} referred by {referred_type} {referred_by} does not exist"""

    fix = "Create the {resource_type}"

    referred_by: str
    referred_type: str
    property_name: str | None = None

    def message(self) -> str:
        return (self.__doc__ or "").format(
            resource_type=self.resource_type,
            identifier=self.identifier,
            referred_type=self.referred_type,
            referred_by=self.referred_by,
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
