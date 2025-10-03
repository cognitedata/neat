from pydantic import BaseModel


class _UndefinedType(BaseModel): ...


class _UnknownType(BaseModel):
    def __str__(self) -> str:
        return "#N/A"

    def __hash__(self) -> int:
        return hash(str(self))


# This is a trick to make Undefined and Unknown singletons
Undefined = _UndefinedType()
Unknown = _UnknownType()


PREFIX_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$"
SUFFIX_PATTERN = r"^[a-zA-Z0-9._~?@!$&'*+,;=%-]+$"
VERSION_PATTERN = r"^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$"
