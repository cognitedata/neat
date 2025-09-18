from typing import Any

from cognite.neat.core._data_model.transformers._base import VerifiedDataModelTransformer


class DataModelTransformerPlugin:
    """This class is used as an interface for data model transformer plugins.
    Any plugin that is used for transforming data models should inherit from this class.
    It is expected to implement the `configure` method which returns a configured transformer.
    """

    def configure(self, **kwargs: Any) -> VerifiedDataModelTransformer:
        """Return a configure plugin for data model import.

        Args:
            **kwargs (Any): Additional keyword arguments for configuration.

        Returns:
            VerifiedDataModelTransformer: A configured instance of the VerifiedDataModelTransformer.

        !!! note "Returns"
            The method must return an instance of `VerifiedDataModelTransformer` or its subclasses
            meaning it must implement the `VerifiedDataModelTransformer` interface.
        """

        raise NotImplementedError()
