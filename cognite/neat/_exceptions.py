from ._issues import ModelSyntaxError


class NeatException(Exception):
    """Base class for all exceptions raised by Neat."""

    pass


class DataModelImportError(NeatException):
    """Raised when there is an error importing a model."""

    def __init__(self, errors: list[ModelSyntaxError]) -> None:
        self.errors = errors

    def __str__(self) -> str:
        return f"Model import failed with {len(self.errors)} errors: " + "; ".join(map(str, self.errors))
