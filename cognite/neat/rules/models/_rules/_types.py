from typing import Annotated

from pydantic import BeforeValidator, Field

StrOrList = Annotated[
    str | list[str],
    BeforeValidator(lambda v: v.replace(", ", ",").split(",") if isinstance(v, str) and v else v),
]


StrList = Annotated[
    list[str],
    BeforeValidator(lambda v: [entry.strip() for entry in v.split(",")] if isinstance(v, str) else v),
]

ExternalID = Annotated[
    str,
    Field(min_items=1, max_items=255),
]
