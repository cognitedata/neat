from typing import Any, Literal

from cognite.neat.core._data_model.transformers._converters import (
    PrefixEntities,
    StandardizeNaming,
    StandardizeSpaceAndVersion,
    ToCompliantEntities,
)
from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._utils.auxiliary import filter_kwargs_by_method
from cognite.neat.plugins._manager import get_plugin_manager
from cognite.neat.plugins.data_model.transformers._base import DataModelTransformerPlugin
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import session_class_wrapper

InternalTransformerName = Literal[
    "cdf_compliant_external_ids", "prefix", "standardize_naming", "standardize_space_and_version"
]


@session_class_wrapper
class TransformAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self, name: str, **kwargs: Any) -> IssueList:
        """Provides access to internal data model transformers and external data model
        transformer plugins.

        Args:
            name (str): The name of format (e.g. Excel) transformer is handling.
            io (str | Path | | DataModelIdentifier | None): The input/output interface for the transformer.
            **kwargs (Any): Additional keyword arguments for the transformer.

        !!! note "kwargs"
            Users must consult the documentation of the transformer to understand
            what keyword arguments are supported.
        """

        # Clean the input name once before matching.
        clean_name: InternalTransformerName | str = name.strip().lower()

        # The match statement cleanly handles each case.
        match clean_name:
            case "cdf_compliant_external_ids":
                return self.cdf_compliant_external_ids()

            case "prefix":
                return self.prefix(**filter_kwargs_by_method(kwargs, self.prefix))

            case "standardize_naming":
                return self.standardize_naming()

            case "standardize_space_and_version":
                return self.standardize_space_and_version()

            case _:  # The wildcard '_' acts as the default 'else' case.
                return self._plugin(name, **kwargs)

    def _plugin(self, name: str, **kwargs: Any) -> IssueList:
        """Provides access to the external plugins for data model importing.

        Args:
            name (str): The name of format (e.g. Excel) plugin is handling.
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for the plugin.

        !!! note "kwargs"
            Users must consult the documentation of the plugin to understand
            what keyword arguments are supported.
        """

        self._state._raise_exception_if_condition_not_met(
            "Data Model Read",
            empty_data_model_store_required=False,
        )

        plugin_manager = get_plugin_manager()
        plugin = plugin_manager.get(name, DataModelTransformerPlugin)

        print(
            f"You are using an external plugin {plugin.__name__}, which is not developed by the NEAT team."
            "\nUse it at your own risk."
        )

        return self._state.data_model_transform(plugin().configure(**kwargs))

    def cdf_compliant_external_ids(self) -> IssueList:
        """Convert conceptual data model component external ids to CDF compliant ids."""
        return self._state.data_model_transform(ToCompliantEntities())

    def prefix(self, prefix: str) -> IssueList:
        """Prefix all views in the data model with the given prefix.

        Args:
            prefix: The prefix to add to the views in the data model.
        """

        return self._state.data_model_transform(PrefixEntities(prefix))  # type: ignore[arg-type]

    def standardize_naming(self) -> IssueList:
        """Standardize the naming of all views/concepts/properties in the data model.

        For concepts/views/containers, the naming will be standardized to PascalCase.
        For properties, the naming will be standardized to camelCase.
        """
        return self._state.data_model_transform(StandardizeNaming())

    def standardize_space_and_version(self) -> IssueList:
        """Standardize space and version in the data model.

        This method will standardize the space and version in the data model to the Cognite standard.
        """
        return self._state.data_model_transform(StandardizeSpaceAndVersion())
