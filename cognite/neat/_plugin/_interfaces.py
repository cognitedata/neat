from abc import ABC, abstractmethod
from typing import Any

from cognite.neat._data_model.importers._base import DMSImporter


class NeatPlugin(ABC):
    @abstractmethod
    def configure(self, *args: Any, **kwargs: Any) -> Any:
        """A method that all plugins must implement."""
        raise NotImplementedError()


class DataModelImporterPlugin(NeatPlugin):
    """This class is used an interface for data model import plugins.
    Any plugin that is used for importing data models should inherit from this class.
    It is expected to implement the `configure` method which returns a configured importer.
    """

    def configure(self, io: str | None, **kwargs: Any) -> DMSImporter:
        """Return a configure plugin for data model import.
        Args:
            io (str): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for configuration.

        Returns:
            DMSImporter: An instance of typically subclassed DMSImporter, specialized for given plugin
        """

        raise NotImplementedError()
