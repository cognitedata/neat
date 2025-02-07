from abc import ABC
from dataclasses import dataclass

from cognite.neat._issues import NeatError


@dataclass(unsafe_hash=True)
class SpreadsheetError(NeatError, ValueError, ABC):
    """In row {row}: {error}"""
    row: int
    error: NeatError
    column: str | None = None

    def as_message(self, include_type: bool = True) -> str:
        if self.column:
            return f"In row {self.row}, column {self.column}: {self.error.as_message(include_type)}"
        return self.__doc__.format(row=self.row, error=self.error.as_message(include_type))


@dataclass(unsafe_hash=True)
class MetadataValueError(SpreadsheetError):
    field_name: str | None = None

    def as_message(self, include_type: bool = True) -> str:
        if self.field_name:
            return f"In row {self.row}, metadata field {self.field_name}: {self.error.as_message(include_type)}"
        return self.__doc__.format(row=self.row, error=self.error.as_message(include_type))


@dataclass(unsafe_hash=True)
class ViewValueError(SpreadsheetError):
    ...


@dataclass(unsafe_hash=True)
class ContainerValueError(SpreadsheetError):
    ...


@dataclass(unsafe_hash=True)
class PropertyValueError(SpreadsheetError):
    ...

@dataclass(unsafe_hash=True)
class ClassValueError(SpreadsheetError):
    ...

@dataclass(unsafe_hash=True)
class EnumValueError(SpreadsheetError):
    ...


@dataclass(unsafe_hash=True)
class NodeValueError(SpreadsheetError):
    ...
