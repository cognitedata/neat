from abc import ABC
from dataclasses import dataclass
from typing import ClassVar, cast

from cognite.neat.v0.core._issues import NeatError
from cognite.neat.v0.core._utils.spreadsheet import SpreadsheetRead


@dataclass(unsafe_hash=True)
class SpreadsheetError(NeatError, ValueError, ABC):
    """In row {row}: {error}"""

    _name: ClassVar[str] = ""
    error: NeatError

    @classmethod
    def create(
        cls, location: tuple[int | str, ...], error: NeatError, spreadsheet: SpreadsheetRead | None = None
    ) -> "SpreadsheetError":
        spreadsheet_name = cast(str, location[0])
        if spreadsheet_name not in ERROR_CLS_BY_SPREADSHEET_NAME:
            # This happens for the metadata sheet, which are individual fields
            if spreadsheet_name == "Metadata" and len(location) >= 2 and isinstance(location[1], str):
                field_name = cast(str, location[1])
            else:
                field_name = spreadsheet_name
            return MetadataValueError(error, field_name=field_name)

        error_cls = ERROR_CLS_BY_SPREADSHEET_NAME[spreadsheet_name]
        row, column = cast(tuple[int, str], location[2:4])

        if spreadsheet:
            row = spreadsheet.adjusted_row_number(row)

        return error_cls(
            row=row,
            error=error,
            column=column,
        )


@dataclass(unsafe_hash=True)
class SpreadsheetListError(SpreadsheetError, ABC):
    """In row {row}, column '{column}': {error}"""

    row: int
    column: str


@dataclass(unsafe_hash=True)
class MetadataValueError(SpreadsheetError):
    """In field {field_name}: {error}"""

    _type: ClassVar[str] = "Metadata"
    field_name: str


@dataclass(unsafe_hash=True)
class ViewValueError(SpreadsheetListError):
    _name = "Views"


@dataclass(unsafe_hash=True)
class ContainerValueError(SpreadsheetListError):
    _name = "Containers"


@dataclass(unsafe_hash=True)
class PropertyValueError(SpreadsheetListError):
    _name = "Properties"


@dataclass(unsafe_hash=True)
class ConceptValueError(SpreadsheetListError):
    _name = "Concepts"


@dataclass(unsafe_hash=True)
class EnumValueError(SpreadsheetListError):
    _name = "Enum"


@dataclass(unsafe_hash=True)
class NodeValueError(SpreadsheetListError):
    _name = "Nodes"


ERROR_CLS_BY_SPREADSHEET_NAME = {cls_._name: cls_ for cls_ in SpreadsheetListError.__subclasses__()}

# Efficient way to set docstring for all classes
for _cls in ERROR_CLS_BY_SPREADSHEET_NAME.values():
    _cls.__doc__ = SpreadsheetListError.__doc__
del _cls
