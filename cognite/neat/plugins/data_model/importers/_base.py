from typing import Any

from cognite.neat.core._data_model.importers._base import BaseImporter


class DataModelImporterPlugin:
    def __init__(self) -> None:
        pass

    def configure(self, io: Any, **kwargs: Any) -> BaseImporter:
        """Return a configure plugin for data model import.

        Args:
            io (Any): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for configuration.

        Returns:
            BaseImporter: A configured instance of the BaseImporter.

        !!! note "Returns"
            The method must return an instance of `BaseImporter` or its subclasses
            meaning it must implement the `BaseImporter` interface.
        """

        raise NotImplementedError()
