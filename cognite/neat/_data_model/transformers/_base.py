from abc import ABC, abstractmethod

from cognite.neat._data_model.models.dms._schema import RequestSchema


class Transformer(ABC):
    """Abstract base class for data model transformers."""

    @abstractmethod
    def transform(self, data_model: RequestSchema) -> RequestSchema:
        """Transform and return the modified data model."""
        raise NotImplementedError()
