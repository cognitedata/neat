from cognite.neat._data_model.models.conceptual._data_model import DataModel as ConceptualDataModel
from cognite.neat._data_model.models.dms._data_model import DataModel as PhysicalDataModel

from ._instances import Instances
from ._provenance import Provenance


class NeatStore:
    def __init__(
        self,
        instances: Instances | None = None,
        conceptual: list[ConceptualDataModel] | None = None,
        physical: list[PhysicalDataModel] | None = None,
    ):
        self.instances = instances
        self.conceptual = conceptual or []
        self.physical = physical or []

        self.provenance = Provenance()

    def read(self) -> None:
        """Read object from the store"""
        ...

    def write(self) -> None:
        """Write object into the store"""
        ...

    def transform(self) -> None:
        """Transfom object in the store"""
        ...
