import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from pydantic_core import ErrorDetails
from rdflib import Namespace

from cognite.neat.issues import MultiValueError
from cognite.neat.utils.spreadsheet import SpreadsheetRead

from .base import DefaultPydanticError, NeatValidationError

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

__all__ = [
    "InvalidSheetError",
    "InvalidRowError",
    "InvalidPropertyError",
    "InvalidClassError",
    "PrefixNamespaceCollisionError",
    "InvalidContainerError",
    "InvalidViewError",
    "InvalidRowUnknownSheetError",
    "NonExistingContainerError",
    "NonExistingViewError",
    "ClassNoPropertiesNoParentError",
    "InconsistentContainerDefinitionError",
    "MultiValueTypeError",
    "MultiValueIsListError",
    "MultiNullableError",
    "MultiDefaultError",
    "MultiIndexError",
    "MultiUniqueConstraintError",
]


@dataclass(frozen=True)
class InvalidSheetError(NeatValidationError, ABC):
    @classmethod
    @abstractmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
    ) -> Self:
        raise NotImplementedError

    @classmethod
    def from_pydantic_errors(
        cls,
        errors: list[ErrorDetails],
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
        **kwargs: Any,
    ) -> "list[NeatValidationError]":
        output: list[NeatValidationError] = []
        for error in errors:
            if raised_error := error.get("ctx", {}).get("error"):
                if isinstance(raised_error, MultiValueError):
                    for caught_error in raised_error.errors:
                        reader = (read_info_by_sheet or {}).get("Properties", SpreadsheetRead())
                        if isinstance(caught_error, InconsistentContainerDefinitionError):
                            row_numbers = list(caught_error.row_numbers)
                            # The Error classes are immutable, so we have to reuse the set.
                            caught_error.row_numbers.clear()
                            for row_no in row_numbers:
                                # Adjusting the row number to the actual row number in the spreadsheet
                                caught_error.row_numbers.add(reader.adjusted_row_number(row_no))
                        if isinstance(caught_error, InvalidRowError):
                            # Adjusting the row number to the actual row number in the spreadsheet
                            new_row = reader.adjusted_row_number(caught_error.row)
                            # The error is frozen, so we have to use __setattr__ to change the row number
                            object.__setattr__(caught_error, "row", new_row)
                        output.append(caught_error)  # type: ignore[arg-type]
                    continue

            if len(error["loc"]) >= 4:
                sheet_name, *_ = error["loc"]
                error_cls = _INVALID_ROW_ERROR_BY_SHEET_NAME.get(str(sheet_name), InvalidRowUnknownSheetError)
                output.append(error_cls.from_pydantic_error(error, read_info_by_sheet))
                continue

            output.append(DefaultPydanticError.from_pydantic_error(error))
        return output


@dataclass(frozen=True)
@total_ordering
class InvalidRowError(InvalidSheetError, ABC):
    description: ClassVar[str] = "This is a generic class for all invalid row specifications."
    fix: ClassVar[str] = "Follow the instruction in the error message."
    sheet_name: ClassVar[str]

    column: str
    row: int
    type: str
    msg: str
    input: Any
    url: str | None

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, InvalidRowError):
            return NotImplemented
        return (self.sheet_name, self.row, self.column) < (
            other.sheet_name,
            other.row,
            other.column,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, InvalidRowError):
            return NotImplemented
        return (self.sheet_name, self.row, self.column) == (
            other.sheet_name,
            other.row,
            other.column,
        )

    @classmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
    ) -> Self:
        sheet_name, _, row, column, *__ = error["loc"]
        reader = (read_info_by_sheet or {}).get(str(sheet_name), SpreadsheetRead())
        return cls(
            column=str(column),
            row=reader.adjusted_row_number(int(row)),
            type=error["type"],
            msg=error["msg"],
            input=error.get("input"),
            url=str(url) if (url := error.get("url")) else None,
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["sheet_name"] = self.sheet_name
        output["column"] = self.column
        output["row"] = self.row
        output["type"] = self.type
        output["msg"] = self.msg
        output["input"] = self.input
        output["url"] = self.url
        return output

    def message(self) -> str:
        input_str = str(self.input) if self.input is not None else ""
        input_str = input_str[:50] + "..." if len(input_str) > 50 else input_str
        output = (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: {self.msg}. "
            f"[type={self.type}, input_value={input_str}]"
        )
        if self.url:
            output += f" For further information visit {self.url}"
        return output


@dataclass(frozen=True)
class InvalidPropertyError(InvalidRowError):
    sheet_name = "Properties"


@dataclass(frozen=True)
class InvalidClassError(InvalidRowError):
    sheet_name = "Classes"


@dataclass(frozen=True)
class InvalidContainerError(InvalidRowError):
    sheet_name = "Containers"


@dataclass(frozen=True)
class InvalidViewError(InvalidRowError):
    sheet_name = "Views"


@dataclass(frozen=True)
class InvalidRowUnknownSheetError(InvalidRowError):
    sheet_name = "Unknown"

    actual_sheet_name: str

    @classmethod
    def from_pydantic_error(
        cls,
        error: ErrorDetails,
        read_info_by_sheet: dict[str, SpreadsheetRead] | None = None,
    ) -> Self:
        sheet_name, _, row, column, *__ = error["loc"]
        reader = (read_info_by_sheet or {}).get(str(sheet_name), SpreadsheetRead())
        try:
            return cls(
                column=str(column),
                row=reader.adjusted_row_number(int(row)),
                actual_sheet_name=str(sheet_name),
                type=error["type"],
                msg=error["msg"],
                input=error.get("input"),
                url=str(url) if (url := error.get("url")) else None,
            )
        except ValueError:
            return DefaultPydanticError.from_pydantic_error(error)  # type: ignore[return-value]

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["actual_sheet_name"] = self.actual_sheet_name
        return output


_INVALID_ROW_ERROR_BY_SHEET_NAME = {
    cls_.sheet_name: cls_ for cls_ in InvalidRowError.__subclasses__() if cls_ is not InvalidRowError
}


@dataclass(frozen=True)
class NonExistingContainerError(InvalidPropertyError):
    description = "The container referenced by the property is missing in the container sheet"
    fix = "Add the container to the container sheet"

    container_id: ContainerId

    def message(self) -> str:
        return (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: The container with "
            f"id {self.container_id} is missing in the container sheet."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["container_id"] = self.container_id
        return output


@dataclass(frozen=True)
class NonExistingViewError(InvalidPropertyError):
    description = "The view referenced by the property is missing in the view sheet"
    fix = "Add the view to the view sheet"

    view_id: ViewId

    def message(self) -> str:
        return (
            f"In {self.sheet_name}, row={self.row}, column={self.column}: The view with "
            f"id {self.view_id} is missing in the view sheet."
        )

    def dump(self) -> dict[str, Any]:
        output = super().dump()
        output["view_id"] = self.view_id
        return output


@dataclass(frozen=True)
class PropertiesDefinedForUndefinedClassesError(NeatValidationError):
    description = "Properties are defined for undefined classes."
    fix = "Make sure to define class in the Classes sheet."

    classes: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["classes"] = self.classes
        return output

    def message(self) -> str:
        return (
            f"Classes {', '.join(self.classes)} have properties assigned to them, but"
            " they are not defined in the Classes sheet."
        )


@dataclass(frozen=True)
class ClassNoPropertiesNoParentError(NeatValidationError):
    description = "Class has no properties and no parents."
    fix = "Check if the class should have properties or parents."

    classes: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["classes"] = self.classes
        return output

    def message(self) -> str:
        if len(self.classes) > 1:
            return f"Classes {', '.join(self.classes)} have no direct or inherited properties. This may be a mistake."
        return f"Class {self.classes[0]} have no direct or inherited properties. This may be a mistake."


@dataclass(frozen=True)
class ParentClassesNotDefinedError(NeatValidationError):
    description = "Parent classes are not defined."
    fix = "Check if the parent classes are defined in Classes sheet."

    classes: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["classes"] = self.classes
        return output

    def message(self) -> str:
        if len(self.classes) > 1:
            return f"Parent classes {', '.join(self.classes)} are not defined. This may be a mistake."
        return f"Parent classes {', '.join(self.classes[0])} are not defined. This may be a mistake."


@dataclass(frozen=True)
class PrefixNamespaceCollisionError(NeatValidationError):
    description = "Same namespaces are assigned to different prefixes."
    fix = "Make sure that each unique namespace is assigned to a unique prefix"

    namespaces: list[Namespace]
    prefixes: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["prefixes"] = self.prefixes
        output["namespaces"] = self.namespaces
        return output

    def message(self) -> str:
        return (
            f"Namespaces {', '.join(self.namespaces)} are assigned multiple times."
            f" Impacted prefixes: {', '.join(self.prefixes)}."
        )


@dataclass(frozen=True)
class ValueTypeNotDefinedError(NeatValidationError):
    description = "Value types referred by properties are not defined in Rules."
    fix = "Make sure that all value types are defined in Rules."

    value_types: list[str]

    def dump(self) -> dict[str, list[str]]:
        output = super().dump()
        output["classes"] = self.value_types
        return output

    def message(self) -> str:
        if len(self.value_types) > 1:
            return f"Value types {', '.join(self.value_types)} are not defined. This may be a mistake."
        return f"Value types {', '.join(self.value_types[0])} are not defined. This may be a mistake."


@dataclass(frozen=True)
class InconsistentContainerDefinitionError(NeatValidationError, ABC):
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


@dataclass(frozen=True)
class MultiValueTypeError(InconsistentContainerDefinitionError):
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


@dataclass(frozen=True)
class MultiValueIsListError(InconsistentContainerDefinitionError):
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


@dataclass(frozen=True)
class MultiNullableError(InconsistentContainerDefinitionError):
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


@dataclass(frozen=True)
class MultiDefaultError(InconsistentContainerDefinitionError):
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


@dataclass(frozen=True)
class MultiIndexError(InconsistentContainerDefinitionError):
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


@dataclass(frozen=True)
class MultiUniqueConstraintError(InconsistentContainerDefinitionError):
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
