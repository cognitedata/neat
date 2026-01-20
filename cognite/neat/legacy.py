import importlib

from cognite.neat._v0.core._issues.errors._general import NeatImportError

from ._version import __version__

try:
    _ = importlib.import_module("rdflib")
except ImportError as e:
    raise NeatImportError("legacy subpackage", "legacy") from e

from cognite.neat._v0.core._utils.auth import get_cognite_client
from cognite.neat._v0.session._base import NeatSession

__all__ = ["NeatSession", "__version__", "get_cognite_client"]
