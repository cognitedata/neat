from abc import ABC, abstractmethod
from typing import ClassVar, TypeVar

from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    ...


class Data(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)


T_Input = TypeVar("T_Input", bound=Data)

T_Output = TypeVar("T_Output", bound=Data)


class Step(ABC):
    def __init__(self):
        self.log: bool = False

    @abstractmethod
    def run(self, *input_data: T_Input) -> T_Output:
        ...
