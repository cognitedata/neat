import importlib

from cognite.neat._exceptions import NeatImportError

try:
    importlib.import_module("rdflib")
    # Legacy is installed, allow v0 tests
except ImportError as e:
    raise NeatImportError("legacy module", "legacy") from e


from cognite.neat._v0.core._utils.auth import get_cognite_client
from cognite.neat._v0.session._base import NeatSession

from ._version import __version__

__all__ = ["NeatSession", "__version__", "get_cognite_client"]
