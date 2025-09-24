import inspect
from abc import ABC, abstractmethod
from functools import lru_cache
from types import UnionType
from typing import Generic, TypeVar, Union, get_args, get_origin

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model._shared import (
    DataModel,
    ImportedDataModel,
    VerifiedDataModel,
)
from cognite.neat.v0.core._data_model.models import (
    UnverifiedConceptualDataModel,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.v0.core._store._provenance import Agent as ProvenanceAgent

T_DataModelIn = TypeVar("T_DataModelIn", bound=DataModel)
T_DataModelOut = TypeVar("T_DataModelOut", bound=DataModel)
T_VerifiedIn = TypeVar("T_VerifiedIn", bound=VerifiedDataModel)
T_VerifiedOut = TypeVar("T_VerifiedOut", bound=VerifiedDataModel)


class DataModelTransformer(ABC, Generic[T_DataModelIn, T_DataModelOut]):
    """This is the base class for all data model transformers."""

    @abstractmethod
    def transform(self, data_model: T_DataModelIn) -> T_DataModelOut:
        """Transform the input data model into the output data model."""
        raise NotImplementedError()

    @property
    def agent(self) -> ProvenanceAgent:
        """Provenance agent for the importer."""
        return ProvenanceAgent(id_=DEFAULT_NAMESPACE[f"agent/{type(self).__name__}"])

    @property
    def description(self) -> str:
        """Get the description of the transformer."""
        return "MISSING DESCRIPTION"

    def is_valid_input(self, data_model: T_DataModelIn) -> bool:
        """Check if the input data model is valid."""
        types = self.transform_type_hint()
        for type_ in types:
            if get_origin(type_) is ImportedDataModel:
                inner = get_args(type_)[0]
                if isinstance(data_model, ImportedDataModel) and isinstance(data_model.unverified_data_model, inner):
                    return True
            elif isinstance(data_model, type_):
                return True
        return False

    @classmethod
    @lru_cache(maxsize=1)
    def transform_type_hint(cls) -> tuple[type, ...]:
        # This is an expensive operation, so we cache the result
        signature = inspect.signature(cls.transform)
        annotation = signature.parameters["data_model"].annotation
        if isinstance(annotation, TypeVar):
            if annotation.__bound__ is None:
                raise TypeError(f"TypeVar {annotation} must be bound to a type.")
            annotation = annotation.__bound__
        # The annotation can be a type or a generic
        if get_origin(annotation) in [UnionType, Union]:
            return get_args(annotation)

        if get_origin(annotation) is ImportedDataModel and isinstance(get_args(annotation)[0], TypeVar):
            # Hardcoded for now, as we only have two types of imported data models
            return (
                ImportedDataModel[UnverifiedPhysicalDataModel],
                ImportedDataModel[UnverifiedConceptualDataModel],
            )

        return (annotation,)


class VerifiedDataModelTransformer(DataModelTransformer[T_VerifiedIn, T_VerifiedOut], ABC): ...
