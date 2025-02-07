from abc import ABC
from dataclasses import dataclass
from typing import ClassVar, cast

from cognite.neat._issues import NeatError
from cognite.neat._utils.spreadsheet import SpreadsheetRead


@dataclass(unsafe_hash=True)
class SpreadsheetError(NeatError, ValueError, ABC):
    """In row {row}: {error}"""

    _name: ClassVar[str] = ""
    row: int
    error: NeatError
    column: str | None = None

    def as_message(self, include_type: bool = True) -> str:
        if self.column:
            return f"In row {self.row}, column {self.column}: {self.error.as_message(include_type)}"
        # We now have a __doc__ attribute, so we can use it directly
        return self.__doc__.format(row=self.row, error=self.error.as_message(include_type))  # type: ignore[union-attr]

    @classmethod
    def create(
        cls, location: tuple[int | str, ...], error: NeatError, spreadsheet: SpreadsheetRead | None = None
    ) -> "SpreadsheetError":
        spreadsheet_name = cast(str, location[0])
        error_cls = ERROR_CLS_BY_SPREADSHEET_NAME[spreadsheet_name]
        if error_cls is MetadataValueError:
            raise NotImplementedError("MetadataValueError is not implemented")
        else:
            row, column = cast(tuple[int, str], location[2:4])

        if spreadsheet:
            row = spreadsheet.adjusted_row_number(row)

        return error_cls(
            row=row,
            error=error,
            column=column,
        )


@dataclass(unsafe_hash=True)
class MetadataValueError(SpreadsheetError):
    _type: ClassVar[str] = "Metadata"
    field_name: str | None = None

    def as_message(self, include_type: bool = True) -> str:
        if self.field_name:
            return f"In row {self.row}, metadata field {self.field_name}: {self.error.as_message(include_type)}"
        # We now have a __doc__ attribute, so we can use it directly
        return SpreadsheetError.__doc__.format(row=self.row, error=self.error.as_message(include_type))  # type: ignore[union-attr]


@dataclass(unsafe_hash=True)
class ViewValueError(SpreadsheetError):
    _name = "Views"


@dataclass(unsafe_hash=True)
class ContainerValueError(SpreadsheetError):
    _name = "Containers"


@dataclass(unsafe_hash=True)
class PropertyValueError(SpreadsheetError):
    _name = "Properties"


@dataclass(unsafe_hash=True)
class ClassValueError(SpreadsheetError):
    _name = "Classes"


@dataclass(unsafe_hash=True)
class EnumValueError(SpreadsheetError):
    _name = "Enum"


@dataclass(unsafe_hash=True)
class NodeValueError(SpreadsheetError):
    _name = "Nodes"


ERROR_CLS_BY_SPREADSHEET_NAME = {cls_._name: cls_ for cls_ in SpreadsheetError.__subclasses__()}
