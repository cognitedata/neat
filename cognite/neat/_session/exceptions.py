import functools
import warnings
from collections.abc import Callable
from typing import Any

from cognite.neat._alpha import ExperimentalFeatureWarning
from cognite.neat._issues.errors import CDFMissingClientError, NeatImportError
from cognite.neat._issues.errors._external import OxigraphStorageLockedError
from cognite.neat._issues.errors._general import NeatValueError

from ._collector import _COLLECTOR

try:
    from rich import print
    from rich.markup import escape

    _ERROR_PREFIX = "[bold red][ERROR][/bold red]"
    _WARNING_PREFIX = "[bold bright_magenta][WARNING][/bold bright_magenta]"
except ImportError:
    _ERROR_PREFIX = "[ERROR]"
    _WARNING_PREFIX = "[WARNING]"

    def escape(x: Any, *_: Any, **__: Any) -> Any:  # type: ignore[misc]
        return x


class NeatSessionError(Exception):
    """Base class for all exceptions raised by the NeatSession class."""

    ...


def _session_method_wrapper(func: Callable, cls_name: str):
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        _COLLECTOR.track_session_command(f"{cls_name}.{func.__name__}", *args, **kwargs)
        try:
            with warnings.catch_warnings(record=True) as w:
                result = func(*args, **kwargs)
                for warning in w:
                    if isinstance(warning.message, ExperimentalFeatureWarning):
                        print(f"{_WARNING_PREFIX} {warning.message}")

            return result
        except NeatSessionError as e:
            action = _get_action()
            print(f"{_ERROR_PREFIX} Cannot {action}: {e}")
        except (
            CDFMissingClientError,
            NeatImportError,
            NeatValueError,
            OxigraphStorageLockedError,
        ) as e:
            print(f"{_ERROR_PREFIX} {escape(e.as_message())}")
        except ModuleNotFoundError as e:
            if e.name == "neatengine":
                action = _get_action()
                print(f"{_ERROR_PREFIX} The functionality {action} requires the NeatEngine.")
            else:
                raise e

    def _get_action():
        action = func.__name__
        if action == "__call__":
            action = func.__qualname__.removesuffix(".__call__").removesuffix("API")
        return action

    return wrapper


def session_class_wrapper(cls: type):
    """This decorator wraps all methods of a class.

    It should be used with all composition classes used with the NeatSession class.

    It does the following:
        * Intercepts all NeatSession exceptions and prints them in a user-friendly way.
        * Collects user metrics.

    Args:
        cls: NeatSession composition class

    Returns:
        cls: NeatSession composition class with all methods wrapped
    """
    to_check = [cls]
    while to_check:
        cls = to_check.pop()
        for attr_name in dir(cls):
            if attr_name.startswith("_") and not attr_name == "__call__":
                continue
            attr = getattr(cls, attr_name)
            if callable(attr):
                setattr(cls, attr_name, _session_method_wrapper(attr, cls.__name__))
            elif isinstance(attr, type):
                to_check.append(attr)
    return cls
