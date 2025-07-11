from pathlib import Path
from typing import Any

from cognite.neat.core._data_model.importers._base import BaseImporter


class DataModelImporterPlugin:
    """This class is used an interface for data model import plugins.
    Any plugin that is used for importing data models should inherit from this class.
    It is expected to implement the `configure` method which returns a configured importer.
    """

    def configure(self, io: str | Path | None, **kwargs: Any) -> BaseImporter:
        """Return a configure plugin for data model import.

        Args:
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for configuration.

        Returns:
            BaseImporter: A configured instance of the BaseImporter.

        !!! note "Returns"
            The method must return an instance of `BaseImporter` or its subclasses
            meaning it must implement the `BaseImporter` interface.
        """

        raise NotImplementedError()
