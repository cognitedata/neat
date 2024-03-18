from abc import ABC
from dataclasses import dataclass

from .base import NeatValidationError, ValidationWarning

__all__ = [
    "ModelImportWarning",
    "UnknownComponentWarning",
    "UnknownSubComponentWarning",
    "IgnoredComponentWarning",
    "UnknownPropertyWarning",
    "ModelImportError",
    "InvalidComponentError",
    "MissingParentDefinitionError",
    "MissingIdentifierError",
    "UnsupportedPropertyTypeError",
]


@dataclass(frozen=True)
class ModelImportWarning(ValidationWarning, ABC):
    description = "A warning was raised during importing."


@dataclass(frozen=True)
class UnknownComponentWarning(ModelImportWarning):
    description = "Unknown component this will be ignored in the imports."
    fix = "Check if the component is defined in the source file."

    component_type: str
    instance_name: str | None = None
    instance_id: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["component_type"] = self.component_type
        output["instance_name"] = self.instance_name
        output["instance_id"] = self.instance_id
        return output

    def message(self) -> str:
        if self.instance_name:
            prefix = f"Unknown component of type'{self.component_type}' with name '{self.instance_name}'."
        else:
            prefix = f"Unknown component '{self.component_type}'"
        return f"{prefix} This will be ignored in the imports."


@dataclass(frozen=True)
class UnknownSubComponentWarning(UnknownComponentWarning):
    sub_component: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["sub_component"] = self.sub_component
        return output

    def message(self) -> str:
        if self.instance_name:
            prefix = f"Unknown sub-component of type'{self.component_type}' with name '{self.instance_name}'."
        else:
            prefix = f"Unknown sub-component '{self.component_type}'"
        return f"{prefix} This will be ignored in the imports."


@dataclass(frozen=True)
class IgnoredComponentWarning(ModelImportWarning):
    description = "This will be ignored in the imports."
    fix = "No fix is available. "

    reason: str
    identifier: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["reason"] = self.reason
        output["identifier"] = self.identifier
        return output

    def message(self) -> str:
        if self.identifier:
            prefix = f"Identifier '{self.identifier}.' is ignored."
        else:
            prefix = "This is ignored."
        return f"{prefix} {self.reason}"


@dataclass(frozen=True)
class UnknownPropertyWarning(ValidationWarning):
    description = "Unknown property this will be ignored in the imports."
    fix = "Check if the property is defined in the DTDL file."

    component_type: str
    property_name: str
    instance_name: str | None = None
    instance_id: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["component_type"] = self.component_type
        output["property_name"] = self.property_name
        output["instance_name"] = self.instance_name
        output["instance_id"] = self.instance_id
        return output

    def message(self) -> str:
        if self.instance_name:
            prefix = (
                f"Unknown property '{self.property_name}' of component "
                f"'{self.component_type}' with name '{self.instance_name}'."
            )
        else:
            prefix = f"Unknown property '{self.property_name}' of component '{self.component_type}'"
        return f"{prefix} This will be ignored in the imports."


@dataclass(frozen=True)
class ModelImportError(NeatValidationError, ABC):
    description = "An error was raised during importing."
    fix = "No fix is available."


@dataclass(frozen=True)
class InvalidComponentError(ModelImportError, ABC):
    description = "This is a base class for all errors related invalid component definitions"
    fix = "Check if the component is defined in the DTDL file."

    component_type: str
    instance_name: str | None = None
    instance_id: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["component_type"] = self.component_type
        output["instance_name"] = self.instance_name
        output["instance_id"] = self.instance_id
        return output


@dataclass(frozen=True)
class MissingParentDefinitionError(InvalidComponentError):
    description = "The parent component is missing"
    fix = "Check if the parent component is defined in the DTDL file."

    def message(self) -> str:
        if self.instance_name:
            return f"Parent component '{self.component_type}' with name '{self.instance_name}' is missing."
        else:
            return f"Parent component '{self.component_type}' is missing."


@dataclass(frozen=True)
class MissingIdentifierError(InvalidComponentError):
    description = "The identifier is missing"
    fix = "Check if the identifier is defined in the DTDL file."

    component_type: str
    instance_name: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["component_type"] = self.component_type
        output["instance_name"] = self.instance_name
        return output

    def message(self) -> str:
        if self.instance_name:
            return f"Identifier for component '{self.component_type}' with name '{self.instance_name}' is missing."
        else:
            return f"Identifier for component '{self.component_type}' is missing."


@dataclass(frozen=True)
class UnsupportedPropertyTypeError(ModelImportError):
    description = "The property type is not supported"
    fix = "Check if the property type is defined in the DTDL file."
    component_type: str
    property_name: str
    property_type: str
    instance_name: str | None = None
    instance_id: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["component_type"] = self.component_type
        output["property_name"] = self.property_name
        output["property_type"] = self.property_type
        output["instance_name"] = self.instance_name
        output["instance_id"] = self.instance_id
        return output

    def message(self) -> str:
        if self.instance_name:
            return (
                f"Property '{self.property_name}' of type '{self.property_type}' "
                f"of instance '{self.instance_name}' ({self.component_type}) is not supported."
            )
        else:
            return (
                f"Property '{self.property_name}' of type '{self.property_type}' "
                f"of instance '{self.instance_id}' ({self.component_type}) is not supported."
            )
