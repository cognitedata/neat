from abc import abstractmethod
from typing import Any, Generic

from cognite.neat.core._data_model._shared import T_UnverifiedDataModel
from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.physical._unverified import (
    UnverifiedPhysicalDataModel,
)


class DataModelImporterPlugin(Generic[T_UnverifiedDataModel]):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    @abstractmethod
    def import_data_model(self, source: Any, *args: Any, **kwargs: Any) -> T_UnverifiedDataModel:
        """Return a dictionary representation of the object."""
        raise NotImplementedError()


class ConceptualDataModelImporterPlugin(DataModelImporterPlugin[UnverifiedConceptualDataModel]):
    def import_data_model(self, source: Any, *args: Any, **kwargs: Any) -> UnverifiedConceptualDataModel:
        """Extract and return a conceptual data model."""
        raise NotImplementedError()


class PhysicalDataModelImporterPlugin(DataModelImporterPlugin[UnverifiedPhysicalDataModel]):
    def import_data_model(self, source: Any, *args: Any, **kwargs: Any) -> UnverifiedPhysicalDataModel:
        """Extract and return a physical data model."""
        raise NotImplementedError()
