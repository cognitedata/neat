from typing import Annotated, Any

from pydantic import BeforeValidator


def str_as_bool(value: Any) -> Any:
    if isinstance(value, str):
        val = value.lower()
        if val in {"true", "1", "yes"}:
            return True
        if val in {"false", "0", "no"}:
            return False
    return value


Bool = Annotated[bool, BeforeValidator(str_as_bool, str)]
