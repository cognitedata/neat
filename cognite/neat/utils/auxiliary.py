import importlib
from types import ModuleType

from cognite.neat.exceptions import NeatImportError


def local_import(module: str, extra: str) -> ModuleType:
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise NeatImportError(module.split(".")[0], extra) from e
