from dataclasses import dataclass
from typing import Any

from cognite.neat.issues import NeatError, NeatWarning

__all__ = [
    "FailedAuthorizationError",
    "MissingDataModelError",
    "FailedConvertError",
    "InvalidClassWarning",
    "InvalidInstanceError",
]


@dataclass(frozen=True)
class FailedAuthorizationError(NeatError):
    description = "Missing authorization for {action}: {reason}"

    action: str
    reason: str

    def message(self) -> str:
        return self.description.format(action=self.action, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["action"] = self.action
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class MissingDataModelError(NeatError):
    description = "The data model with identifier {identifier} is missing: {reason}"
    fix = "Check the data model identifier and try again."

    identifier: str
    reason: str

    def message(self) -> str:
        return self.description.format(identifier=self.identifier, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["identifier"] = self.identifier
        output["reason"] = self.reason
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
class InvalidClassWarning(NeatWarning):
    description = "The class {class_name} is invalid and will be skipped. {reason}"
    fix = "Check the error message and correct the class."

    class_name: str
    reason: str

    def message(self) -> str:
        return self.description.format(class_name=self.class_name, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["class_name"] = self.class_name
        output["reason"] = self.reason
        return output


@dataclass(frozen=True)
class InvalidInstanceError(NeatError):
    description = "The {type_} with identifier {identifier} is invalid and will be skipped. {reason}"
    fix = "Check the error message and correct the instance."

    type_: str
    identifier: str
    reason: str

    def message(self) -> str:
        return self.description.format(type_=self.type_, identifier=self.identifier, reason=self.reason)

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["type"] = self.type_
        output["identifier"] = self.identifier
        output["reason"] = self.reason
        return output
