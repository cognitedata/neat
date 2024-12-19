"""These are special exceptions that are used by the store to signal invalid transformers"""

from dataclasses import dataclass


class NeatStoreError(Exception):
    """Base class for all exceptions in the store module"""

    ...


@dataclass
class InvalidInputOperation(NeatStoreError, RuntimeError):
    """Raised when an invalid operation is attempted"""

    expected: tuple[type, ...]
    got: type


class EmptyStore(NeatStoreError, RuntimeError):
    """Raised when the store is empty"""

    ...
