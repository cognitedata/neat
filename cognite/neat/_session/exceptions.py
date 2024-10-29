import functools
from collections.abc import Callable
from typing import Any

try:
    from rich import print

    _PREFIX = "[bold red][ERROR][/bold red]"
except ImportError:
    _PREFIX = "[ERROR]"


class NeatSessionError(Exception):
    """Base class for all exceptions raised by the NeatSession class."""

    ...


def _intercept_session_exceptions(func: Callable):
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return func(*args, **kwargs)
        except NeatSessionError as e:
            action = func.__name__
            if action == "__call__":
                action = func.__qualname__.removesuffix(".__call__").removesuffix("API")
            print(f"{_PREFIX} Cannot {action}: {e}")

    return wrapper


def intercept_session_exceptions(cls: type):
    to_check = [cls]
    while to_check:
        cls = to_check.pop()
        for attr_name in dir(cls):
            if attr_name.startswith("_") and not attr_name == "__call__":
                continue
            attr = getattr(cls, attr_name)
            if callable(attr):
                setattr(cls, attr_name, _intercept_session_exceptions(attr))
            elif isinstance(attr, type):
                to_check.append(attr)
    return cls
