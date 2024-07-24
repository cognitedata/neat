from abc import ABC
from dataclasses import dataclass
from typing import Any

from .base import ValidationWarning


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
class PropertyRedefinedWarning(ValidationWarning):
    description = "Property, {property}, redefined in {class_}. This will be ignored in the imports."
    fix = "Check if the property is defined only once."

    property_id: str
    class_id: str

    def dump(self) -> dict[str, str]:
        return {"property_id": self.property_id, "class_id": self.class_id}

    def message(self) -> str:
        return self.description.format(property=self.property_id, class_=self.class_id)


@dataclass(frozen=True)
class APIWarning(ModelImportWarning):
    description = "An error was raised."
    fix = "No fix is available."

    error_message: str

    def message(self) -> str:
        return self.error_message

    def dump(self) -> dict[str, str]:
        return {"error_message": self.error_message}


@dataclass(frozen=True)
class FailedImportWarning(ModelImportWarning):
    description = "Failed to import part of the model."
    fix = "No fix is available."

    identifier: set[str]

    def message(self) -> str:
        return f"Failed to import: {self.identifier}. This will be skipped."

    def dump(self) -> dict[str, Any]:
        return {"identifier": list(self.identifier)}
