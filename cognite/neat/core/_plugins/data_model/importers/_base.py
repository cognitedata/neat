from abc import abstractmethod
from typing import Any, Generic

from cognite.neat.core._data_model._shared import T_UnverifiedDataModel


class DataModelImporterPlugin(Generic[T_UnverifiedDataModel]):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    @abstractmethod
    def import_data_model(self, source: Any, *args: Any, **kwargs: Any) -> T_UnverifiedDataModel:
        """Return a dictionary representation of the object."""
        raise NotImplementedError()
