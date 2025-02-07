from warnings import WarningMessage

from cognite.neat._issues._base import NeatError, NeatWarning
from pydantic_core import ErrorDetails
from cognite.neat._utils.spreadsheet import SpreadsheetRead


def from_pydantic_error(errors: list[ErrorDetails], read_info_by_sheet: dict[str, SpreadsheetRead] | None = None) -> list[NeatError]:
    raise NotImplementedError

def from_warning(warn: WarningMessage) -> NeatWarning:
    raise NotImplementedError

    #
    # @dataclass(unsafe_hash=True)
    # class NeatWarning(NeatIssue, UserWarning):
    #     """This is the base class for all warnings used in Neat."""
    #
    #     @classmethod
    #     def from_warning(cls, warning: WarningMessage) -> "NeatWarning":
    #         """Create a NeatWarning from a WarningMessage."""
    #         return DefaultWarning.from_warning_message(warning)
    #
    # @dataclass(unsafe_hash=True)
    # class DefaultWarning(NeatWarning):
    #     """{category}: {warning}"""
    #
    #     extra = "Source: {source}"
    #
    #     warning: str
    #     category: str
    #     source: str | None = None
    #
    #     @classmethod
    #     def from_warning_message(cls, warning: WarningMessage) -> NeatWarning:
    #         if isinstance(warning.message, NeatWarning):
    #             return warning.message
    #
    #         return cls(
    #             warning=str(warning.message),
    #             category=warning.category.__name__,
    #             source=warning.source,
    #         )
    #
    #     def as_message(self, include_type: bool = True) -> str:
    #         return str(self.warning)

# def from_errors(cls, errors: "list[ErrorDetails | NeatError]", ) -> "list[NeatError]":
#     """Convert a list of pydantic errors to a list of Error instances.
#
#     This is intended to be overridden in subclasses to handle specific error types.
#     """
#     all_errors: list[NeatError] = []
#     read_info_by_sheet = kwargs.get("read_info_by_sheet")
#
#     for error in errors:
#         if (
#                 isinstance(error, dict)
#                 and error["type"] == "is_instance_of"
#                 and error["loc"][1] == "is-instance[SheetList]"
#         ):
#             # Skip the error for SheetList, as it is not relevant for the user. This is an
#             # internal class used to have helper methods for a lists as .to_pandas()
#             continue
#
#         neat_error: NeatError | None = None
#         if isinstance(error, dict) and isinstance(ctx := error.get("ctx"), dict) and "error" in ctx:
#             neat_error = ctx["error"]
#         elif isinstance(error, NeatError | MultiValueError):
#             neat_error = error
#
#         loc = error["loc"] if isinstance(error, dict) else tuple()
#         if isinstance(neat_error, MultiValueError):
#             all_errors.extend([cls._adjust_error(e, loc, read_info_by_sheet) for e in neat_error.errors])
#         elif isinstance(neat_error, NeatError):
#             all_errors.append(cls._adjust_error(neat_error, loc, read_info_by_sheet))
#         elif isinstance(error, dict) and len(loc) >= 4 and read_info_by_sheet:
#             all_errors.append(RowError.from_pydantic_error(error, read_info_by_sheet))
#         elif isinstance(error, dict):
#             all_errors.append(DefaultPydanticError.from_pydantic_error(error))
#         else:
#             # This is unreachable. However, in case it turns out to be reachable, we want to know about it.
#             raise ValueError(f"Unsupported error type: {error}")
#     return all_errors
#
# @classmethod
# def _adjust_error(
#         cls, error: "NeatError", loc: tuple[str | int, ...], read_info_by_sheet: dict[str, SpreadsheetRead] | None
# ) -> "NeatError":
#     from .errors._wrapper import MetadataValueError
#
#     if read_info_by_sheet:
#         cls._adjust_row_numbers(error, read_info_by_sheet)
#     if len(loc) == 2 and isinstance(loc[0], str) and loc[0].casefold() == "metadata":
#         return MetadataValueError(field_name=str(loc[1]), error=error)
#     return error
#
# @staticmethod
# def _adjust_row_numbers(caught_error: "NeatError", read_info_by_sheet: dict[str, SpreadsheetRead]) -> None:
#     from cognite.neat._issues.errors._properties import PropertyDefinitionDuplicatedError
#     from cognite.neat._issues.errors._resources import ResourceNotDefinedError
#
#     reader = read_info_by_sheet.get("Properties", SpreadsheetRead())
#
#     if isinstance(caught_error, PropertyDefinitionDuplicatedError) and caught_error.location_name == "rows":
#         adjusted_row_number = (
#                 tuple(
#                     reader.adjusted_row_number(row_no) if isinstance(row_no, int) else row_no
#                     for row_no in caught_error.locations or []
#                 )
#                 or None
#         )
#         # The error is frozen, so we have to use __setattr__ to change the row number
#         object.__setattr__(caught_error, "locations", adjusted_row_number)
#     elif isinstance(caught_error, RowError):
#         # Adjusting the row number to the actual row number in the spreadsheet
#         new_row = reader.adjusted_row_number(caught_error.row)
#         # The error is frozen, so we have to use __setattr__ to change the row number
#         object.__setattr__(caught_error, "row", new_row)
#     elif isinstance(caught_error, ResourceNotDefinedError):
#         if isinstance(caught_error.row_number, int) and caught_error.sheet_name == "Properties":
#             new_row = reader.adjusted_row_number(caught_error.row_number)
#             object.__setattr__(caught_error, "row_number", new_row)
