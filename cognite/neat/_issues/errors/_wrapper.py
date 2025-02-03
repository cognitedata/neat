from abc import ABC
from dataclasses import dataclass

from cognite.neat._issues import NeatError


@dataclass(unsafe_hash=True)
class SpreadsheetError(NeatError, ValueError, ABC):
    location: str
    error: NeatError
    row: int


@dataclass(unsafe_hash=True)
class MetadataValueError(SpreadsheetError):
    """In {row}, the {location} - {error}"""


@dataclass(unsafe_hash=True)
class ViewValueError(SpreadsheetError):
    """View {view_name} - {error}"""

    location: str
    error: NeatError
