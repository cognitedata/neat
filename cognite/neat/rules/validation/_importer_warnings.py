from dataclasses import dataclass

from ._base import ValidationWarning


@dataclass(frozen=True, order=True)
class UnknownComponent(ValidationWarning):
    description = "Unknown component this will be ignored in the imports."
    fix = "Check if the component is defined in the DTDL file."

    component_name: str
    instance_name: str | None = None
    instance_id: str | None = None

    def dump(self) -> dict[str, str | None]:
        output = super().dump()
        output["component_name"] = self.component_name
        output["instance_name"] = self.instance_name
        output["instance_id"] = self.instance_id
        return output

    def message(self) -> str:
        if self.instance_name:
            prefix = f"Unknown component of type'{self.component_name}' with name '{self.instance_name}'."
        else:
            prefix = f"Unknown component '{self.component_name}'"
        return f"{prefix} This will be ignored in the imports."
