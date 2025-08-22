from typing import Literal

from cognite.neat.core._data_model.models.entities._restrictions import parse_restriction
from cognite.neat.core._data_model.transformers._converters import (
    AddPropertiesFromRestriction,
    SubsetConceptualDataModelOnRestrictions,
)
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import session_class_wrapper


@session_class_wrapper
class TransformAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def filter_on_restrictions(
        self,
        restrictions: str | list[str],
        only_concepts_with_properties: bool = True,
        include_dangling_properties: bool = False,
        include_ancestors: bool = False,
        include_different_space: bool = False,
        operation: Literal["and", "or"] = "and",
    ):
        """
        Filter the data model based on specified restrictions.
        Args:
            restrictions (str | list[str]): Single restriction string or list of restriction strings
                to filter the data model. Each restriction will be parsed and applied.
            only_concepts_with_properties (bool, optional): If True, only include concepts that have
                properties. Defaults to True.
            include_dangling_properties (bool, optional): If True, include properties that may not
                be connected to concepts. Defaults to False.
            include_ancestors (bool, optional): If True, include ancestor concepts in the filtered
                result (i.e. implements). Defaults to False.
            include_different_space (bool, optional): If True, concepts from different
                spaces will be considered. Defaults to False.
            operation (Literal["and", "or"], optional): Logical operation to apply when multiple
                restrictions are provided. Use "and" for intersection or "or" for union.
                Defaults to "and".
        Returns:
            The transformed data model state after applying the specified restrictions and filters.
        """

        if isinstance(restrictions, str):
            restrictions = [restrictions]

        restrictions = [parse_restriction(r.strip()) for r in restrictions if r.strip()]

        return self._state.data_model_transform(
            SubsetConceptualDataModelOnRestrictions(
                restrictions,
                only_concepts_with_properties=only_concepts_with_properties,
                include_dangling_properties=include_dangling_properties,
                include_ancestors=include_ancestors,
                include_different_space=include_different_space,
                operation=operation,
            )
        )

    def add_properties_from_restrictions(
        self,
        restrictions: str | list[str],
        depth: int = 1,
    ):
        """
        Add properties to the data model based on specified restrictions.
        Args:
            restrictions (str | list[str]): Single restriction string or list of restriction strings
                to filter the data model. Each restriction will be parsed and applied.
            depth (int, optional): Depth of the hierarchy to consider when adding properties.
                Defaults to 1.
        Returns:
            The transformed data model state after applying the specified restrictions and adding properties.
        """

        if isinstance(restrictions, str):
            restrictions = [restrictions]

        restrictions = {parse_restriction(r.strip()) for r in restrictions if r.strip()}

        return self._state.data_model_transform(
            AddPropertiesFromRestriction(
                restrictions,
                depth=depth,
            )
        )
