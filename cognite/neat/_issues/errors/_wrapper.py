from dataclasses import dataclass

from cognite.neat._issues import NeatError


@dataclass(unsafe_hash=True)
class MetadataValueError(NeatError, ValueError):
    """Field {field_name} - {error}"""

    field_name: str
    error: NeatError
