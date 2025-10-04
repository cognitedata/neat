from collections.abc import Callable

from pydantic import ValidationError
from pydantic_core import ErrorDetails


def humanize_validation_error(
    error: ValidationError, location_fun: Callable[[tuple[int | str, ...]], str] | None = None
) -> list[str]:
    """Converts a ValidationError to a human-readable format.

    This overwrites the default error messages from Pydantic to be better suited for Toolkit users.

    Args:
        error: The ValidationError to convert.
        location_fun: Optional function to convert the location tuple to a string prefix for each error message.
            If provided, this function will be called with the location tuple and should return a string.
            This is useful for example if the json path should be translated to row/column in a table.

    Returns:
        A list of human-readable error messages.
    """
    errors: list[str] = []
    item: ErrorDetails

    for item in error.errors(include_input=True, include_url=False):
        loc = item["loc"]
        error_type = item["type"]
        if error_type == "missing":
            msg = f"Missing required field: {loc[-1]!r}"
        elif error_type == "extra_forbidden":
            msg = f"Unused field: {loc[-1]!r}"
        elif error_type == "value_error":
            msg = str(item["ctx"]["error"])
        elif error_type == "literal_error":
            msg = f"{item['msg']}. Got {item['input']!r}."
        elif error_type == "string_type":
            msg = (
                f"{item['msg']}. Got {item['input']!r} of type {type(item['input']).__name__}. "
                f"Hint: Use double quotes to force string."
            )
        elif error_type == "model_type":
            model_name = item["ctx"].get("class_name", "unknown")
            msg = (
                f"Input must be an object of type {model_name}. Got {item['input']!r} of "
                f"type {type(item['input']).__name__}."
            )
        elif error_type.endswith("_type"):
            msg = f"{item['msg']}. Got {item['input']!r} of type {type(item['input']).__name__}."
        else:
            # Default to the Pydantic error message
            msg = item["msg"]

        if error_type.endswith("dict_type") and len(loc) > 1:
            # If this is a dict_type error for a JSON field, the location will be:
            #  dict[str,json-or-python[json=any,python=tagged-union[list[...],dict[str,...],str,bool,int,float,none]]]
            #  This is hard to read, so we simplify it to just the field name.
            loc = tuple(["dict" if isinstance(x, str) and "json-or-python" in x else x for x in loc])

        error_suffix = f"{msg[:1].casefold()}{msg[1:]}"
        if location_fun is not None:
            prefix = location_fun(loc)
            msg = f"{prefix} {error_suffix}"
        elif len(loc) > 1 and error_type in {"extra_forbidden", "missing"}:
            # We skip the last element as this is in the message already
            msg = f"In {as_json_path(loc[:-1])} {error_suffix}"
        elif len(loc) > 1:
            msg = f"In {as_json_path(loc)} {error_suffix}"
        elif len(loc) == 1 and isinstance(loc[0], str) and error_type not in {"extra_forbidden", "missing"}:
            msg = f"In field {loc[0]} {error_suffix}"
        errors.append(msg)
    return errors


def as_json_path(loc: tuple[str | int, ...]) -> str:
    """Converts a location tuple to a JSON path.

    Args:
        loc: The location tuple to convert.

    Returns:
        A JSON path string.
    """
    if not loc:
        return ""
    # +1 to convert from 0-based to 1-based indexing
    prefix = ""
    if isinstance(loc[0], int):
        prefix = "item "

    suffix = ".".join([str(x) if isinstance(x, str) else f"[{x + 1}]" for x in loc]).replace(".[", "[")
    return f"{prefix}{suffix}"
