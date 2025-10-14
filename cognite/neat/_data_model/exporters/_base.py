from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from cognite.neat._data_model.models.dms import RequestSchema

T_Export = TypeVar("T_Export")


class DMSExporter(ABC, Generic[T_Export]):
    """This is the base class for all DMS exporters."""

    NEW_LINE = "\n"
    ENCODING = "utf-8"

    @abstractmethod
    def export(self, data_model: RequestSchema) -> T_Export:
        raise NotImplementedError()
