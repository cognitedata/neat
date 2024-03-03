from abc import ABC
from dataclasses import dataclass

from cognite.client import data_modeling as dm

from ._base import Error


@dataclass(frozen=True, order=True)
class InconsistentContainerDefinition(Error, ABC):
    description = "This is a base class for all errors related to inconsistent container definitions"
    fix = "Ensure all properties using the same container have the same type, constraints, and indexes."
    container: dm.ContainerId
    property_name: str
    row_numbers: list[int]


@dataclass(frozen=True, order=True)
class MultiValueTypeDefinition(InconsistentContainerDefinition):
    description = "The property has multiple value types"
    fix = "Use the same value type for all properties using the same container."
    value_types: list[str]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {self.row_numbers} "
            f"has different value types: {self.value_types}"
        )


@dataclass(frozen=True, order=True)
class MultiValueIsListDefinition(InconsistentContainerDefinition):
    description = "The property has multiple list definitions"
    fix = "Use the same list definition for all properties using the same container."
    list_definitions: list[bool]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {self.row_numbers} "
            f"has different list definitions: {self.list_definitions}"
        )


@dataclass(frozen=True, order=True)
class MultiNullableDefinition(InconsistentContainerDefinition):
    description = "The property has multiple nullable definitions"
    fix = "Use the same nullable definition for all properties using the same container."
    nullable_definitions: list[bool]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {self.row_numbers} "
            f"has different nullable definitions: {self.nullable_definitions}"
        )


@dataclass(frozen=True, order=True)
class MultiDefaultDefinition(InconsistentContainerDefinition):
    description = "The property has multiple default definitions"
    fix = "Use the same default definition for all properties using the same container."
    default_definitions: list[str | int | dict | None]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {self.row_numbers} "
            f"has different default definitions: {self.default_definitions}"
        )


@dataclass(frozen=True, order=True)
class MultiIndexDefinition(InconsistentContainerDefinition):
    description = "The property has multiple index definitions"
    fix = "Use the same index definition for all properties using the same container."
    index_definitions: list[str]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {self.row_numbers} "
            f"has different index definitions: {self.index_definitions}"
        )


@dataclass(frozen=True, order=True)
class MultiUniqueConstraintDefinition(InconsistentContainerDefinition):
    description = "The property has multiple unique constraint definitions"
    fix = "Use the same unique constraint definition for all properties using the same container."
    unique_constraint_definitions: list[str]

    def message(self) -> str:
        return (
            f"{self.container}.{self.property_name} defined in rows: {self.row_numbers} "
            f"has different unique constraint definitions: {self.unique_constraint_definitions}"
        )
