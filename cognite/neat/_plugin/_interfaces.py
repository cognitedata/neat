from abc import ABC, abstractmethod
from typing import Any, ClassVar

from cognite.neat._data_model.importers._base import DMSImporter


class NeatPlugin(ABC):
    _entry_point: ClassVar[str] = "cognite.neat.plugin"
    method_name: ClassVar[str] = "plugin_name"

    @abstractmethod
    def configure(self, **kwargs: Any) -> Any:
        """A method that all plugins must implement."""
        raise NotImplementedError()


class PhysicalDataModelReaderPlugin(NeatPlugin):
    """This class is used an interface for data model import plugins.
    Any plugin that is used for importing data models should inherit from this class.
    It is expected to implement the `configure` method which returns a configured importer.

    _entry_point not to be changed by any consecutive plugin, as it is used for plugin registration and retrieval
    """

    _entry_point: ClassVar[str] = "cognite.neat.plugin.data_model.readers"

    def configure(self, **kwargs: Any) -> DMSImporter:
        """Return a configure plugin for data model import.
        Args:
            **kwargs (Any): Keyword arguments for plugin configuration.
                            The specific arguments depend on the plugin implementation.
        Returns:
            DMSImporter: An instance of typically subclassed DMSImporter, specialized for given plugin
        """

        raise NotImplementedError()


class PhysicalDataModelWriterPlugin(NeatPlugin):
    """This class is used an interface for data model export plugins.
    Any plugin that is used for exporting data models should inherit from this class.
    It is expected to implement the `configure` method which returns a configured exporter.

    _entry_point not to be changed by any consecutive plugin, as it is used for plugin registration and retrieval
    """

    _entry_point: ClassVar[str] = "cognite.neat.plugin.data_model.writers"

    def configure(self, **kwargs: Any) -> Any:
        """Return a configure plugin for data model export.
        Args:
            **kwargs (Any): Keyword arguments for plugin configuration.
                            The specific arguments depend on the plugin implementation.
        Returns:
            Any: An instance of typically subclassed exporter, specialized for given plugin
        """

        raise NotImplementedError()
