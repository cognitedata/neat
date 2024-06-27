import importlib
import inspect
from collections.abc import Callable
from types import ModuleType

from cognite.neat.exceptions import NeatImportError


def local_import(module: str, extra: str) -> ModuleType:
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise NeatImportError(module.split(".")[0], extra) from e


def get_classmethods(cls: type) -> list[Callable]:
    return [
        func for _, func in inspect.getmembers(cls, lambda x: inspect.ismethod(x) and not x.__name__.startswith("_"))
    ]
