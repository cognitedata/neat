from abc import ABC
from dataclasses import dataclass

from ._base import Error


@dataclass(frozen=True, order=True)
class InvalidComponent(Error, ABC):
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


@dataclass(frozen=True, order=True)
class MissingParentDefinition(InvalidComponent):
    description = "The parent component is missing"
    fix = "Check if the parent component is defined in the DTDL file."

    def message(self) -> str:
        if self.instance_name:
            return f"Parent component '{self.component_type}' with name '{self.instance_name}' is missing."
        else:
            return f"Parent component '{self.component_type}' is missing."
