from dataclasses import dataclass

from ._base import ValidationWarning


@dataclass(frozen=True, order=True)
class UnknownComponent(ValidationWarning):
    description = "Unknown component this will be ignored in the imports."
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

    def message(self) -> str:
        if self.instance_name:
            prefix = f"Unknown component of type'{self.component_type}' with name '{self.instance_name}'."
        else:
            prefix = f"Unknown component '{self.component_type}'"
        return f"{prefix} This will be ignored in the imports."


@dataclass(frozen=True, order=True)
class UnknownSubComponent(UnknownComponent):
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


@dataclass(frozen=True, order=True)
class ImportIgnored(ValidationWarning):
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


@dataclass(frozen=True, order=True)
class UnknownProperty(ValidationWarning):
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
