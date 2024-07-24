from abc import ABC
from dataclasses import dataclass

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
