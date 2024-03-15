from abc import ABC
from dataclasses import dataclass
from typing import Any

from cognite.client import data_modeling as dm

from ._base import Error


@dataclass(frozen=True, order=True)
class InconsistentContainerDefinition(Error, ABC):
    description = "This is a base class for all errors related to inconsistent container definitions"
    fix = "Ensure all properties using the same container have the same type, constraints, and indexes."
    container: dm.ContainerId
    property_name: str
    row_numbers: set[int]

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output.update(
            {
                "container": self.container.dump(),
                "property_name": self.property_name,
                "row_numbers": sorted(self.row_numbers),
            }
        )
        return output


@dataclass(frozen=True, order=True)
class MultiValueTypeDefinitions(InconsistentContainerDefinition):
    description = "The property has multiple value types"
    fix = "Use the same value type for all properties using the same container."
    value_types: set[str]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {sorted(self.row_numbers)} "
            f"has different value types: {self.value_types}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["value_types"] = sorted(self.value_types)
        return output


@dataclass(frozen=True, order=True)
class MultiValueIsListDefinitions(InconsistentContainerDefinition):
    description = "The property has multiple list definitions"
    fix = "Use the same list definition for all properties using the same container."
    list_definitions: set[bool]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {sorted(self.row_numbers)} "
            f"has different list definitions: {self.list_definitions}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["list_definitions"] = sorted(self.list_definitions)
        return output


@dataclass(frozen=True, order=True)
class MultiNullableDefinitions(InconsistentContainerDefinition):
    description = "The property has multiple nullable definitions"
    fix = "Use the same nullable definition for all properties using the same container."
    nullable_definitions: set[bool]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {sorted(self.row_numbers)} "
            f"has different nullable definitions: {self.nullable_definitions}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["nullable_definitions"] = sorted(self.nullable_definitions)
        return output


@dataclass(frozen=True, order=True)
class MultiDefaultDefinitions(InconsistentContainerDefinition):
    description = "The property has multiple default definitions"
    fix = "Use the same default definition for all properties using the same container."
    default_definitions: list[str | int | dict | None]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {sorted(self.row_numbers)} "
            f"has different default definitions: {self.default_definitions}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["default_definitions"] = self.default_definitions
        return output


@dataclass(frozen=True, order=True)
class MultiIndexDefinitions(InconsistentContainerDefinition):
    description = "The property has multiple index definitions"
    fix = "Use the same index definition for all properties using the same container."
    index_definitions: set[str]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {sorted(self.row_numbers)} "
            f"has different index definitions: {self.index_definitions}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["index_definitions"] = sorted(self.index_definitions)
        return output


@dataclass(frozen=True, order=True)
class MultiUniqueConstraintDefinitions(InconsistentContainerDefinition):
    description = "The property has multiple unique constraint definitions"
    fix = "Use the same unique constraint definition for all properties using the same container."
    unique_constraint_definitions: set[str]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {sorted(self.row_numbers)} "
            f"has different unique constraint definitions: {self.unique_constraint_definitions}"
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["unique_constraint_definitions"] = sorted(self.unique_constraint_definitions)
        return output
