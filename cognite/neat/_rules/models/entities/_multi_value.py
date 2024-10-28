from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    model_serializer,
    model_validator,
)

from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.data_types import DataType

from ._constants import _PARSE, Undefined
from ._single_value import ClassEntity, UnknownEntity


class MultiValueTypeInfo(BaseModel):
    type_: ClassVar[EntityTypes] = EntityTypes.multi_value_type
    types: list[DataType | ClassEntity]

    def __str__(self) -> str:
        return " | ".join([str(t) for t in self.types])

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    @classmethod
    def load(cls, data: Any) -> "MultiValueTypeInfo":
        # already instance of MultiValueTypeInfo
        if isinstance(data, cls):
            return data

        # it is a raw string that needs to be parsed
        elif isinstance(data, str):
            return cls.model_validate({_PARSE: data})

        # it is dict that needs to be parsed
        else:
            return cls.model_validate(data)

    @model_validator(mode="before")
    def _load(cls, data: Any) -> "dict | MultiValueTypeInfo":
        if isinstance(data, dict) and _PARSE in data:
            data = data[_PARSE]
        elif isinstance(data, dict):
            return data
        else:
            raise ValueError(f"Cannot load {cls.__name__} from {data}")

        result = cls._parse(data)
        return result

    @classmethod
    def _parse(cls, raw: str) -> dict:
        if not (types := [type_.strip() for type_ in raw.split("|")]):
            return {"types": [UnknownEntity()]}
        else:
            return {
                "types": [
                    (DataType.load(type_) if DataType.is_data_type(type_) else ClassEntity.load(type_))
                    for type_ in types
                ]
            }

    def set_default_prefix(self, prefix: str):
        for type_ in self.types:
            if isinstance(type_, ClassEntity) and type_.prefix is Undefined:
                type_.prefix = prefix

    def is_multi_object_type(self) -> bool:
        """Will signalize to DMS converter to create connection to unknown Node type"""
        return all(isinstance(t, ClassEntity) for t in self.types)

    def is_multi_data_type(self) -> bool:
        """Will signalize to DMS converter to attempt to find the best data type for value"""
        return all(isinstance(t, DataType) for t in self.types)

    def is_mixed_type(self) -> bool:
        """Will signalize to DMS converter to fall back to string"""
        return not self.is_multi_object_type() and not self.is_multi_data_type()
