from abc import ABC
from dataclasses import dataclass
from typing import Any

from .base import NeatValidationError, ValidationWarning

__all__ = [
    "ModelImportWarning",
    "UnknownComponentWarning",
    "UnknownSubComponentWarning",
    "IgnoredComponentWarning",
    "UnknownPropertyWarning",
    "UnknownValueTypeWarning",
    "MissingContainerWarning",
    "MissingContainerPropertyWarning",
    "MultipleDataModelsWarning",
    "UnknownPropertyTypeWarning",
    "FailedToInferValueTypeWarning",
    "MoreThanOneNonAlphanumericCharacterWarning",
    "UnknownContainerConstraintWarning",
    "NoDataModelError",
    "ModelImportError",
    "InvalidComponentError",
    "MissingParentDefinitionError",
    "MissingIdentifierError",
    "UnsupportedPropertyTypeError",
    "APIError",
    "FailedImportWarning",
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
class UnknownValueTypeWarning(ModelImportWarning):
    description = "Unknown value type. This limits validation done by NEAT. "
    fix = "Set the value type"
    class_id: str
    property_id: str

    def dump(self) -> dict[str, str]:
        return {"class_id": self.class_id, "property_id": self.property_id}

    def message(self) -> str:
        return (
            f"Unknown value type for property '{self.property_id}' of class '{self.class_id}'. "
            "This limits validation done by NEAT."
        )


@dataclass(frozen=True)
class MultipleDataModelsWarning(ModelImportWarning):
    description = "Multiple data models detected. This is not supported."
    fix = "Remove the extra data models."

    data_models: list[str]

    def message(self) -> str:
        return f"Multiple data models detected: {self.data_models}. Will only import the first one."

    def dump(self) -> dict[str, list[str]]:
        return {"data_models": self.data_models}


@dataclass(frozen=True)
class MissingContainerWarning(ModelImportWarning):
    description = "Missing container definition."
    fix = "Add a container definition."

    view_id: str
    property_: str
    container_id: str

    def message(self) -> str:
        return (
            f"Container '{self.container_id}' is missing. "
            f"Will skip property '{self.property_}' of view '{self.view_id}'."
        )

    def dump(self) -> dict[str, str]:
        return {"view_id": self.view_id, "property": self.property_, "container_id": self.container_id}


@dataclass(frozen=True)
class MissingContainerPropertyWarning(ModelImportWarning):
    description = "Missing container property definition."
    fix = "Add a container property definition."

    view_id: str
    property_: str
    container_id: str

    def message(self) -> str:
        return (
            f"Container '{self.container_id}' is missing property '{self.property_}'. "
            f"This property will be skipped for view '{self.view_id}'."
        )

    def dump(self) -> dict[str, str]:
        return {"view_id": self.view_id, "property": self.property_, "container_id": self.container_id}


@dataclass(frozen=True)
class UnknownPropertyTypeWarning(ModelImportWarning):
    description = "Unknown property type. This will be ignored in the imports."
    fix = "Set to a supported property type."
    view_id: str
    property_id: str
    property_type: str

    def message(self) -> str:
        return (
            f"Unknown property type '{self.property_type}' for property '{self.property_id}' "
            f"of view '{self.view_id}'. This will be ignored in the imports."
        )

    def dump(self) -> dict[str, str]:
        return {"view_id": self.view_id, "property_id": self.property_id, "property_type": self.property_type}


@dataclass(frozen=True)
class UnknownContainerConstraintWarning(ModelImportWarning):
    description = "Unknown container constraint. This will be ignored in the imports."
    fix = "Set to a supported container constraint."
    container_id: str
    property_id: str
    constraint: str

    def message(self) -> str:
        return (
            f"Unknown container constraint '{self.constraint}' for property '{self.property_id}' of container "
            f"'{self.container_id}'. This will be ignored in the imports."
        )

    def dump(self) -> dict[str, str]:
        return {"container_id": self.container_id, "property_id": self.property_id, "constraint": self.constraint}


@dataclass(frozen=True)
class FailedToInferValueTypeWarning(ModelImportWarning):
    description = "Failed to infer value type. This will be ignored in the imports."
    fix = "Set to a supported value type."
    view_id: str
    property_id: str

    def message(self) -> str:
        return (
            f"Failed to infer value type for property '{self.property_id}' of view '{self.view_id}'. "
            f"This will be ignored in the imports."
        )

    def dump(self) -> dict[str, str]:
        return {"view_id": self.view_id, "property_id": self.property_id}


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


@dataclass(frozen=True)
class MoreThanOneNonAlphanumericCharacterWarning(ModelImportWarning):
    description = """This warning is raised when doing regex validation of strings which either represent class ids,
    property ids, prefix, data model name, that contain more than one non-alphanumeric character,
    such as for example '_' or '-'."""

    field_name: str
    value: str

    def message(self) -> str:
        return f"Field {self.field_name} with value {self.value} contains more than one non-alphanumeric character!"

    def dump(self) -> dict[str, str]:
        return {"field_name": self.field_name, "value": self.value}


@dataclass(frozen=True)
class ModelImportError(NeatValidationError, ABC):
    description = "An error was raised during importing."
    fix = "No fix is available."


@dataclass(frozen=True)
class NoDataModelError(ModelImportError):
    description = "No data model found.."
    fix = "Check if the data model exists in the source."

    error_message: str

    def message(self) -> str:
        return self.error_message

    def dump(self) -> dict[str, str]:
        return {"error_message": self.error_message}


@dataclass(frozen=True)
class APIError(ModelImportError):
    description = "An error was raised during importing."
    fix = "No fix is available."

    error_message: str

    def message(self) -> str:
        return self.error_message

    def dump(self) -> dict[str, str]:
        return {"error_message": self.error_message}


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
