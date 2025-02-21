from typing import cast
from warnings import WarningMessage

from pydantic_core import ErrorDetails

from cognite.neat._issues._base import NeatError, NeatWarning
from cognite.neat._utils.spreadsheet import SpreadsheetRead

from .errors import NeatValueError, SpreadsheetError
from .warnings import NeatValueWarning


def from_pydantic_errors(
    errors: list[ErrorDetails], read_info_by_sheet: dict[str, SpreadsheetRead] | None = None
) -> list[NeatError]:
    read_info_by_sheet = read_info_by_sheet or {}
    return [
        _from_pydantic_error(error, read_info_by_sheet)
        for error in errors
        # Skip the error for SheetList, as it is not relevant for the user. This is an
        # internal class used to have helper methods for a lists as .to_pandas()
        if not (error["type"] == "is_instance_of" and error["loc"][1] == "is-instance[SheetList]")
    ]


def from_warning(warning: WarningMessage) -> NeatWarning:
    if isinstance(warning.message, NeatWarning):
        return warning.message
    message = f"{warning.category.__name__}: {warning.message!s}"
    if warning.source:
        message += f" Source: {warning.source}"
    return NeatValueWarning(message)


def _from_pydantic_error(error: ErrorDetails, read_info_by_sheet: dict[str, SpreadsheetRead]) -> NeatError:
    neat_error = _create_neat_value_error(error)
    location = error["loc"]

    # only errors caused in model_validate will have location information
    if location:
        return SpreadsheetError.create(location, neat_error, read_info_by_sheet.get(cast(str, location[0])))

    # errors that occur while for example parsing spreadsheet in input rules
    # will not have location information so we return neat_error as is
    # this is workaround until more elegant solution is found
    return neat_error


def _create_neat_value_error(error: ErrorDetails) -> NeatValueError:
    if (ctx := error.get("ctx")) and (neat_error := ctx.get("error")) and isinstance(neat_error, NeatError):
        # Is already a NeatError
        return neat_error
    return _pydantic_to_neat_error(error)


def _pydantic_to_neat_error(error: ErrorDetails) -> NeatValueError:
    error_type = error["type"]
    input_value = error["input"]
    match error_type:
        # See https://docs.pydantic.dev/latest/errors/validation_errors/ for all possible error types:
        case error_type if error_type.endswith("_type") | error_type.endswith("_parsing"):
            if input_value is None:
                return NeatValueError("value is missing.")
            expected_type = error_type.removesuffix("_type").removesuffix("_parsing")
            return NeatValueError(f"Expected a {expected_type} type, got {input_value!r}")
        case _:
            # The above cases overwrite the human-readable message from pydantic.
            # Motivation for overwriting is that pydantic is developer-oriented and while neat is SME-oriented.
            return NeatValueError(f"{error['msg']} got '{input_value}'")
