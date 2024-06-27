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


def class_html_doc(cls: type, include_factory_methods: bool = True) -> str:
    if cls.__doc__:
        docstring = cls.__doc__.split("Args:")[0].strip().replace("\n", "<br />")
    else:
        docstring = "Missing Description"
    if include_factory_methods:
        factory_methods = get_classmethods(cls)
        if factory_methods:
            factory_methods_str = "".join(f"<li><em>.{m.__name__}</em></li>" for m in factory_methods)
            docstring += (
                f"<br /><strong>Available factory methods:</strong><br />"
                f'<ul style="list-style-type:circle;">{factory_methods_str}</ul>'
            )
    return f"<h3>{cls.__name__}</h3><p>{docstring}</p>"
