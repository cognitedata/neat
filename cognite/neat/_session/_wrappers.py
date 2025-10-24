from collections.abc import Callable
from typing import Any, TypeVar

from pyparsing import wraps

from cognite.neat._utils.text import split_on_capitals

T_Class = TypeVar("T_Class", bound=object)


def session_wrapper(cls: type[T_Class]) -> type[T_Class]:
    # 1. Define the method decorator inside
    def _handle_method_call(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to handle exceptions and print provenance length"""

        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                res = func(self, *args, **kwargs)

                change = self._store.provenance[-1]
                print(
                    f"{' '.join(split_on_capitals(cls.__name__))} - {func.__name__} "
                    f"{'✅' if change.successful else '❌'}"
                    f" | Issues: {len(change.issues) + len(change.errors) if change.issues or change.errors else 0}"
                    f" (of which {len(change.errors) if change.errors else 0} critical)"
                    f"{'\nFor more details run neat.issues()' if change.issues or change.errors else ''}"
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
