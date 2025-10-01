from abc import ABC, abstractmethod

from cognite.neat._data_model.models.dms import RequestSchema


class DMSImporter(ABC):
    """This is the base class for all DMS importers."""

    @abstractmethod
    def to_data_model(self) -> RequestSchema:
        """Convert the imported data to a RequestSchema."""
        raise NotImplementedError()
