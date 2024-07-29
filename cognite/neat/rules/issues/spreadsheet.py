import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import total_ordering
from typing import Any, ClassVar

from pydantic_core import ErrorDetails
from rdflib import Namespace

from cognite.neat.issues import MultiValueError, NeatError
from cognite.neat.issues.errors.resources import MultiplePropertyDefinitionsError, ResourceNotDefinedError
from cognite.neat.utils.spreadsheet import SpreadsheetRead

from .base import DefaultPydanticError, NeatValidationError

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


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
    ) -> "list[NeatError]":
        output: list[NeatError] = []
        for error in errors:
            if raised_error := error.get("ctx", {}).get("error"):
                if isinstance(raised_error, MultiValueError):
                    for caught_error in raised_error.errors:
                        reader = (read_info_by_sheet or {}).get("Properties", SpreadsheetRead())
                        if (
                            isinstance(caught_error, MultiplePropertyDefinitionsError)
                            and caught_error.location_name == "rows"
                        ):
                            adjusted_row_number = tuple(
                                reader.adjusted_row_number(row_no) if isinstance(row_no, int) else row_no
                                for row_no in caught_error.locations
                            )
                            # The error is frozen, so we have to use __setattr__ to change the row number
                            object.__setattr__(caught_error, "locations", adjusted_row_number)
                        if isinstance(caught_error, InvalidRowError):
                            # Adjusting the row number to the actual row number in the spreadsheet
                            new_row = reader.adjusted_row_number(caught_error.row)
                            # The error is frozen, so we have to use __setattr__ to change the row number
                            object.__setattr__(caught_error, "row", new_row)
                        output.append(caught_error)  # type: ignore[arg-type]
                        if isinstance(caught_error, ResourceNotDefinedError):
                            if isinstance(caught_error.row_number, int) and caught_error.sheet_name == "Properties":
                                new_row = reader.adjusted_row_number(caught_error.row_number)
                                object.__setattr__(caught_error, "row_number", new_row)
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
class RegexViolationError(NeatValidationError):
    description = "Value, {value} failed regex, {regex}, validation."
    fix = "Make sure that the name follows the regex pattern."

    value: str
    regex: str

    def dump(self) -> dict[str, str]:
        output = super().dump()
        output["value"] = self.value
        output["regex"] = self.regex
        return output

    def message(self) -> str:
        return self.description.format(value=self.value, regex=self.regex)


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
class DefaultValueTypeNotProperError(NeatValidationError):
    """This exceptions is raised when default value type is not proper, i.e. it is not
    according to the expected value type set in Rules.


    Args:
        default_value_type: default value type that raised exception
        expected_value_type: expected value type that raised exception

    """

    description = (
        "This exceptions is raised when default value type is not proper, i.e. it is not "
        "according to the expected value type set in Rules."
    )
    property_id: str
    default_value_type: str
    expected_value_type: str

    def message(self) -> str:
        message = (
            f"Default value for property {self.property_id} is of type {self.default_value_type} "
            f"which is different from the expected value type {self.expected_value_type}!"
        )
        message += f"\nDescription: {self.description}"
        return message


@dataclass(frozen=True)
class AssetRulesHaveCircularDependencyError(NeatValidationError):
    description = "Asset rules have circular dependencies."
    fix = "Linking between classes via property that maps to parent_external_id must yield hierarchy structure."

    classes: list[str]

    def dump(self) -> dict[str, list[tuple[str, str]]]:
        output = super().dump()
        output["classes"] = self.classes
        return output

    def message(self) -> str:
        return f"Asset rules have circular dependencies between classes {', '.join(self.classes)}."


@dataclass(frozen=True)
class AssetParentPropertyPointsToDataValueTypeError(NeatValidationError):
    description = "Parent property points to a data value type instead of a class."
    fix = "Make sure that the parent property points to a class."

    class_property_with_data_value_type: list[tuple[str, str]]

    def dump(self) -> dict[str, list[tuple[str, str]]]:
        output = super().dump()
        output["class_property"] = self.class_property_with_data_value_type
        return output

    def message(self) -> str:
        text = [
            f"class {class_} property {property_}" for class_, property_ in self.class_property_with_data_value_type
        ]
        return f"Following  {', and'.join(text)} point to data value type instead to classes. This is a mistake."


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
