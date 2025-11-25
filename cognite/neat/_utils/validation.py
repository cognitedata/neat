from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from pydantic_core import ErrorDetails


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
        prefix = "item"

    suffix = ".".join([str(x) if isinstance(x, str) else f"[{x + 1}]" for x in loc]).replace(".[", "[")
    return f"{prefix}{suffix}"


@dataclass
class ValidationContext:
    """
    Context for validation errors providing configuration for error message formatting.

    This class configures how validation errors are reported, including location formatting,
    field naming conventions, and how to present missing required fields.

    Attributes:
        parent_loc: Optional location tuple to prepend to each error location.
            This is useful when the error is for a nested model and you want to include the location
            of the parent model.
        humanize_location: A function that converts a location tuple to a human-readable string.
            The default is `as_json_path`, which converts the location to a JSON path.
            This can for example be replaced when the location comes from an Excel table.
        field_name: The name use for "field" in error messages. Default is "field". This can be changed to
            "column" or "value" to better fit the context.
        field_renaming: Optional mapping of field names to source names.
            This is useful when the field names in the model are different from the names in the source.
            For example, if the model field is "asset_id" but the source column is "Asset ID",
            you can provide a mapping {"asset_id": "Asset ID"} to have the error messages use the source names.
        missing_required_descriptor: How to describe missing required fields. Default is "missing".
            Other option is "empty" which can be more suitable for table data.
    """

    parent_loc: tuple[int | str, ...] = field(default_factory=tuple)
    humanize_location: Callable[[tuple[int | str, ...]], str] = as_json_path
    field_name: Literal["field", "column", "value"] = "field"
    field_renaming: Mapping[str, str] = field(default_factory=dict)
    missing_required_descriptor: Literal["empty", "missing"] = "missing"


def humanize_validation_error(
    error: ErrorDetails,
    context: ValidationContext | None = None,
) -> str:
    """Converts a pydantic ErrorDetails object to a human-readable format.
    This overwrites the default error messages from Pydantic to be better suited for NEAT users.
    Args:
        error: The ErrorDetails object to convert.
        context: The context for humanizing the error.
    Returns:
        A human-readable error message.
    """

    context = context or ValidationContext()

    loc = (*context.parent_loc, *error["loc"])
    type_ = error["type"]

    if type_ == "missing":
        msg = f"Missing required {context.field_name}: {loc[-1]!r}"
    elif type_ == "extra_forbidden":
        msg = f"Unused {context.field_name}: {loc[-1]!r}"
    elif type_ == "value_error":
        msg = str(error["ctx"]["error"])
    elif type_ == "literal_error":
        msg = f"{error['msg']}. Got {error['input']!r}."
    elif type_ == "string_type":
        msg = f"{error['msg']}. Got {error['input']!r} of type {type(error['input']).__name__}. "
    elif type_ == "model_type":
        model_name = error["ctx"].get("class_name", "unknown")
        msg = (
            f"Input must be an object of type {model_name}. Got {error['input']!r} of "
            f"type {type(error['input']).__name__}."
        )
    elif type_ == "union_tag_invalid":
        msg = error["msg"].replace(", 'direct'", "").replace("found using 'type' ", "").replace("tag", "value")
    elif type_ == "string_pattern_mismatch":
        msg = f"string '{error['input']}' does not match the required pattern: '{error['ctx']['pattern']}'."

    elif type_.endswith("_type"):
        msg = f"{error['msg']}. Got {error['input']!r} of type {type(error['input']).__name__}."
    else:
        # Default to the Pydantic error message
        msg = error["msg"]

    if type_.endswith("dict_type") and len(loc) > 1:
        # If this is a dict_type error for a JSON field, the location will be:
        #  dict[str,json-or-python[json=any,python=tagged-union[list[...],dict[str,...],str,bool,int,float,none]]]
        #  This is hard to read, so we simplify it to just the field name.
        loc = tuple(["dict" if isinstance(x, str) and "json-or-python" in x else x for x in loc])

    error_suffix = f"{msg[:1].casefold()}{msg[1:]}"

    if len(loc) >= 3 and context.field_name == "column" and loc[-3:] == ("type", "enum", "values"):
        # Special handling for enum errors in table columns
        msg = _enum_message(type_, loc, context)
    elif len(loc) > 1 and type_ in {"extra_forbidden", "missing"}:
        if context.missing_required_descriptor == "empty" and type_ == "missing":
            # This is a table so we modify the error message.
            msg = (
                f"In {context.humanize_location(loc[:-1])} the {context.field_name}"
                f" {context.field_renaming.get(str(loc[-1]), loc[-1])!r} "
                "cannot be empty."
            )
        else:
            # We skip the last element as this is in the message already
            msg = f"In {context.humanize_location(loc[:-1])} {error_suffix.replace('field', context.field_name)}"
    elif len(loc) > 1:
        if context.parent_loc == ("Metadata",) and len(loc) == 2:
            msg = f"In table '{loc[0]}' '{loc[1]}' {error_suffix}"
        else:
            msg = f"In {context.humanize_location(loc)} {error_suffix}"
    elif len(loc) == 1 and isinstance(loc[0], str) and type_ not in {"extra_forbidden", "missing"}:
        msg = f"In {context.field_name} {loc[0]!r}, {error_suffix}"

    msg = msg.strip()
    if not msg.endswith("."):
        msg += "."
    return msg


def _enum_message(type_: str, loc: tuple[int | str, ...], context: ValidationContext) -> str:
    """Special handling of enum errors in table columns."""

    if loc[-1] != "values":
        raise RuntimeError("This is a neat bug, report to the team.")
    if type_ == "missing":
        return (
            f"In {context.humanize_location(loc[:-1])} definition should include "
            "a reference to a collection in the 'Enum' sheet (e.g., collection='MyEnumCollection')."
        )
    elif type_ == "too_short":
        return f"In {context.humanize_location(loc[:-1])} collection is not defined in the 'Enum' sheet"
    else:
        raise RuntimeError("This is a neat bug, report to the team.")
