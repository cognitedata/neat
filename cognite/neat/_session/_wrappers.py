from collections.abc import Callable
from functools import wraps
from typing import Any, Protocol, TypeVar

from cognite.neat._store._store import NeatStore
from cognite.neat._utils.text import split_on_capitals


class HasStore(Protocol):
    _store: NeatStore


T_Class = TypeVar("T_Class", bound=object)


def session_wrapper(cls: type[T_Class]) -> type[T_Class]:
    # 1. Define the method decorator inside
    def _handle_method_call(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to handle exceptions and print provenance length"""

        @wraps(func)
        def wrapper(self: HasStore, *args: Any, **kwargs: Any) -> Any:
            try:
                res = func(self, *args, **kwargs)
                change = self._store.provenance[-1]

                issues_count = len(change.issues) if change.issues else 0
                errors_count = len(change.errors) if change.errors else 0
                total_issues = issues_count + errors_count

                newline = "\n"  # python 3.10 compatibility
                print(
                    f"{' '.join(split_on_capitals(cls.__name__))} - {func.__name__} "
                    f"{'✅' if change.successful else '❌'}"
                    f" | Issues: {total_issues}"
                    f" (of which {errors_count} critical)"
                    f"{newline + 'For more details run neat.issues()' if change.issues or change.errors else ''}"
                )

                return res

            # if an error occurs, we catch it and print it out instead of
            # getting a full traceback
            except Exception as e:
                print(f"{' '.join(split_on_capitals(cls.__name__))} - {func.__name__} ❌")
                print(f"Error: {e}")

        return wrapper

    # Iterate through all attributes of the class
    for attr_name in dir(cls):
        # Skip private/protected methods (starting with _)
        if not attr_name.startswith("_"):
            attr = getattr(cls, attr_name)
            # Only wrap callable methods
            if callable(attr):
                # Replace the original method with wrapped version
                setattr(cls, attr_name, _handle_method_call(attr))

    # Return the modified class
    return cls
