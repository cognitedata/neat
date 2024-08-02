"""All warnings raised by the neat package are defined here. Note this module is called 'neat_warnings' instead
of 'warnings' to avoid conflicts with the built-in Python warnings module."""

from cognite.neat.issues import NeatWarning

from .external import FileMissingRequiredFieldWarning, FileReadWarning, UnexpectedFileTypeWarning, UnknownItemWarning

__all__ = [
    "FileReadWarning",
    "FileMissingRequiredFieldWarning",
    "UnknownItemWarning",
    "UnexpectedFileTypeWarning",
]

_NEAT_WARNINGS_BY_NAME = {warning.__name__: warning for warning in NeatWarning.__subclasses__()}
