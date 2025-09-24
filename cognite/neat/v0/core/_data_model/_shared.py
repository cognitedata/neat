from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from cognite.neat.v0.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
)
from cognite.neat.v0.core._data_model.models._import_contexts import ImportContext
from cognite.neat.v0.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.v0.core._data_model.models.physical._unverified import (
    UnverifiedPhysicalDataModel,
)

VerifiedDataModel: TypeAlias = ConceptualDataModel | PhysicalDataModel

T_VerifiedDataModel = TypeVar("T_VerifiedDataModel", bound=VerifiedDataModel)
UnverifiedDataModel: TypeAlias = UnverifiedPhysicalDataModel | UnverifiedConceptualDataModel
T_UnverifiedDataModel = TypeVar("T_UnverifiedDataModel", bound=UnverifiedDataModel)


@dataclass
class ImportedDataModel(Generic[T_UnverifiedDataModel]):
    """This class is used to store results of data model import from a source prior to
    verification and validation.

    Attributes:
        unverified_data_model: The unverified data model.
        context: The context of the import, including warnings, errors and any other
                 relevant information.
    """

    unverified_data_model: T_UnverifiedDataModel | None
    context: ImportContext | None = None

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedModel"

    @property
    def display_name(self) -> str:
        if self.unverified_data_model is None:
            return "Failed to load data model"
        return self.unverified_data_model.display_name


ImportedUnverifiedDataModel: TypeAlias = (
    ImportedDataModel[UnverifiedPhysicalDataModel] | ImportedDataModel[UnverifiedConceptualDataModel]
)
T_ImportedUnverifiedDataModel = TypeVar("T_ImportedUnverifiedDataModel", bound=ImportedUnverifiedDataModel)

DataModel: TypeAlias = (
    ConceptualDataModel
    | PhysicalDataModel
    | ImportedDataModel[UnverifiedPhysicalDataModel]
    | ImportedDataModel[UnverifiedConceptualDataModel]
)
T_DataModel = TypeVar("T_DataModel", bound=DataModel)
