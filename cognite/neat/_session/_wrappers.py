from collections.abc import Callable
from functools import wraps
from typing import Any, Protocol, TypeVar

from cognite.neat._session._usage_analytics._collector import Collector
from cognite.neat._store._store import NeatStore
from cognite.neat._utils.text import NEWLINE, split_on_capitals


class HasStore(Protocol):
    _store: NeatStore


T_Class = TypeVar("T_Class", bound=HasStore)

_COLLECTOR = Collector()


def session_wrapper(cls: type[T_Class]) -> type[T_Class]:
    # 1. Define the method decorator inside
    def _handle_method_call(func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to handle exceptions and print provenance length"""

        @wraps(func)
        def wrapper(self: HasStore, *args: Any, **kwargs: Any) -> Any:
            display_name = f"{' '.join(split_on_capitals(cls.__name__))} - {func.__name__}"
            identifier = f"{cls.__name__}.{func.__name__}"
            try:
                res = func(self, *args, **kwargs)
                if not self._store.provenance or "DataModel" not in identifier:
                    print(f"{display_name} ✅")
                    if _COLLECTOR.can_collect:
                        _COLLECTOR.collect("action", {"action": identifier, "success": True})
                    return res
                change = self._store.provenance[-1]
                issues_count = len(change.issues) if change.issues else 0
                errors_count = len(change.errors) if change.errors else 0
                total_issues = issues_count + errors_count

                data_model_not_read = not change.successful and "ReadPhysicalDataModel" in identifier

                print(
                    f"{display_name} "
                    f"{'✅' if change.successful else '❌'}"
                    f"{f' | Issues: {total_issues} (of which {errors_count} critical)' if total_issues > 0 else ''}"
                    f"{NEWLINE + '⚠️ Data model not read into session' if data_model_not_read else ''}"
                    f"{NEWLINE + '📋 For details on issues run neat.issues' if change.issues or change.errors else ''}"
                    f"{NEWLINE + '📊 For details on result run neat.result' if change.result else ''}"
                )
                if _COLLECTOR.can_collect:
                    event = change.as_mixpanel_event()
                    event["action"] = identifier
                    _COLLECTOR.collect("action", event)
                    if change.result:
                        event = change.result.as_mixpanel_event()
                        event["action"] = identifier
                        _COLLECTOR.collect("deployment", event)

                return res

            # if an error occurs, we catch it and print it out instead of
            # getting a full traceback
            except Exception as e:
                print(f"{display_name} ❌")
                print(f"{e!s}")
                if _COLLECTOR.can_collect:
                    _COLLECTOR.collect("action", {"action": identifier, "success": False, "error_message": str(e)})

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
