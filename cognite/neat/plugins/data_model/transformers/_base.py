from pathlib import Path
from typing import Any, Literal

from cognite.neat.core._data_model.transformers import VerifiedDataModelTransformer


class DataModelTransformerPlugin:
    """This class is used an interface for data model transformer plugins.
    Any plugin that is used for transforming data models should inherit from this class.
    It is expected to implement the `configure` method which returns a configured transformer.
    """

    _required_data_model: Literal["ConceptualDataModel", "PhysicalDataModel"] = "ConceptualDataModel"

    def configure(self, io: str | Path | None, **kwargs: Any) -> VerifiedDataModelTransformer:
        """Return a configure plugin for data model transformation.

        Args:
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for configuration.

        Returns:
            BaseImporter: A configured instance of the BaseImporter.

        !!! note "Returns"
            The method must return an instance of `VerifiedDataModelTransformer` or its subclasses
            meaning it must implement the `VerifiedDataModelTransformer` interface.
        """

        raise NotImplementedError()
