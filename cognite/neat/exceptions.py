class NeatException(Exception):
    """Base class for all exceptions raised by NEAT."""

    type_: str
    code: int
    description: str
    example: str
    fix: str
    message: str
