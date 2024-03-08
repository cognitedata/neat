from dataclasses import dataclass

from ._base import ValidationWarning


@dataclass(frozen=True, order=True)
class ClassNoPropertiesNoParents(ValidationWarning):
    description = "Class has no properties and no parents."
    fix = "Check if the class should have properties or parents."

    classes: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["classes"] = self.classes
        return output

    def message(self) -> str:
        if len(self.classes) > 1:
            return f"Classes {', '.join(self.classes)} have no properties and no parents. This may be a mistake."
        return f"Class {self.classes[0]} has no properties and no parents. This may be a mistake."
