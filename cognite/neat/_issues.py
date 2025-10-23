from pydantic import BaseModel


class Issue(BaseModel): ...


class ModelSyntaxError(Issue):
    """If any syntax error is found. Stop validation
    and ask user to fix the syntax error first."""

    message: str


class ImplementationWarning(Issue):
    """This is only for conceptual data model. It means that conversion to DMS
    will fail unless user implements the missing part."""

    message: str
    fix: str


class ConsistencyError(Issue):
    """If any consistency error is found, the deployment of the data model will fail. For example,
    if a reverse direct relations points to a non-existing direct relation. This is only relevant for
    DMS model.
    """

    message: str
    fix: str


class Recommendation(Issue):
    """Best practice recommendation."""

    message: str
    fix: str | None = None
