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
_PARSE = object()
