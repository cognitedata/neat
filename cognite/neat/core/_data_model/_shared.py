from collections.abc import Hashable, ItemsView, Iterator, KeysView, Mapping, ValuesView
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from cognite.neat.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
)
from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.physical._unverified import (
    UnverifiedPhysicalDataModel,
)
from cognite.neat.core._utils.spreadsheet import SpreadsheetRead

VerifiedDataModel: TypeAlias = ConceptualDataModel | PhysicalDataModel

T_VerifiedDataModel = TypeVar("T_VerifiedDataModel", bound=VerifiedDataModel)
UnverifiedDataModel: TypeAlias = UnverifiedPhysicalDataModel | UnverifiedConceptualDataModel
T_UnverifiedDataModel = TypeVar("T_UnverifiedDataModel", bound=UnverifiedDataModel)

T_Key = TypeVar("T_Key", bound=Hashable)
T_Value = TypeVar("T_Value")


class ImportContext(dict, Mapping[T_Key, T_Value]):
    # The below methods are included to make better type hints in the IDE
    def __getitem__(self, k: T_Key) -> T_Value:
        return super().__getitem__(k)

    def __setitem__(self, k: T_Key, v: T_Value) -> None:
        super().__setitem__(k, v)

    def __delitem__(self, k: T_Key) -> None:
        super().__delitem__(k)

    def __iter__(self) -> Iterator[T_Key]:
        return super().__iter__()

    def keys(self) -> KeysView[T_Key]:  # type: ignore[override]
        return super().keys()

    def values(self) -> ValuesView[T_Value]:  # type: ignore[override]
        return super().values()

    def items(self) -> ItemsView[T_Key, T_Value]:  # type: ignore[override]
        return super().items()

    def get(self, __key: T_Key, __default: T_Value = ...) -> T_Value:  # type: ignore[override, assignment]
        return super().get(__key, __default)

    def pop(self, __key: T_Key, __default: T_Value = ...) -> T_Value:  # type: ignore[override, assignment]
        return super().pop(__key, __default)

    def popitem(self) -> tuple[T_Key, T_Value]:
        return super().popitem()


class SpreadsheetContext(ImportContext[str, SpreadsheetRead]):
    def __init__(self, data: dict[str, SpreadsheetRead] | None = None) -> None:
        """Initialize the SpreadsheetContext with a dictionary of SpreadsheetRead objects.

        Args:
            data (dict[str, SpreadsheetRead]): A dictionary where keys are sheet names and values are
                SpreadsheetRead objects containing the read data.
        """
        super().__init__(data or {})
        for k, v in self.items():
            if not isinstance(k, str):
                raise TypeError(f"Expected string key, got {type(k).__name__}")
            if not isinstance(v, SpreadsheetRead):
                raise TypeError(f"Expected SpreadsheetRead for key '{k}', got {type(v).__name__}")


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
