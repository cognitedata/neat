from collections.abc import Callable
from functools import wraps
from typing import Any, Protocol, TypeVar

from cognite.neat._issues import ConsistencyError, Recommendation
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

                recommendation_count = (
                    len(recommendations)
                    if change.issues and (recommendations := change.issues.by_type().get(Recommendation))
                    else 0
                )
                consistency_errors_count = (
                    len(consistency_errors)
                    if change.issues and (consistency_errors := change.issues.by_type().get(ConsistencyError))
                    else 0
                )
                syntax_errors_count = len(change.errors) if change.errors else 0
                errors_count = consistency_errors_count + syntax_errors_count
                total_insights = recommendation_count + consistency_errors_count + syntax_errors_count

                data_model_not_read = not change.successful and "ReadPhysicalDataModel" in identifier

                if not change.successful:
                    success_icon = "❌"
                elif change.successful and consistency_errors_count:
                    success_icon = "⚠️"
                else:
                    success_icon = "✅"

                print(
                    f"{display_name} "
                    f"{success_icon}"
                    f"{f' | Insights: {total_insights} (of which {errors_count} errors)' if total_insights > 0 else ''}"
                    f"{NEWLINE + '⚠️ Data model not read into session' if data_model_not_read else ''}"
                    f"{NEWLINE + '📋 For details on issues run .issues' if change.issues or change.errors else ''}"
                    f"{NEWLINE + '📊 For details on result run .result' if change.result else ''}"
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
    # Intercept __init__ to wrap any methods added via setattr
    original_init = cls.__init__

    @wraps(original_init)
    def pick_alpha_methods(self: HasStore, *args: Any, **kwargs: Any) -> Any:
        """This method wraps any instance methods added during __init__. which is the case for alpha methods"""
        original_init(self, *args, **kwargs)
        # Wrap any instance methods added during init
        for attr_name in dir(self):
            if not attr_name.startswith("_"):
                attr = getattr(self, attr_name, None)
                # Check if it's an instance method (not from the class)
                if callable(attr) and attr_name not in vars(self.__class__):
                    # Wrap and set on the instance
                    wrapped = (
                        _handle_method_call(attr.__func__) if hasattr(attr, "__func__") else _handle_method_call(attr)
                    )
                    setattr(self, attr_name, wrapped.__get__(self, type(self)))

    cls.__init__ = pick_alpha_methods  # type: ignore[assignment]
    return cls
