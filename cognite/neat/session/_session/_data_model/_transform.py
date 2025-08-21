from typing import Any, Literal

import networkx as nx
from IPython.display import HTML, display
from pyvis.network import Network as PyVisNetwork  # type: ignore

from cognite.neat.core._constants import IN_NOTEBOOK, IN_PYODIDE
from cognite.neat.core._data_model.analysis._base import DataModelAnalysis
from cognite.neat.core._data_model.models.entities._restrictions import parse_restriction
from cognite.neat.core._data_model.transformers._converters import SubsetConceptualDataModelOnRestrictions
from cognite.neat.core._utils.io_ import to_directory_compatible
from cognite.neat.core._utils.rdf_ import uri_display_name
from cognite.neat.session._show import _generate_hex_color_per_type
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class TransformAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def filter_on_restrictions(self, 
                 restrictions: str|list[str], only_concepts_with_properties: bool = True,
                 include_dangling_properties: bool = False,                 
                 include_ancestors : bool = False,
                 include_different_space : bool = False,
                 operation: Literal["and", "or"] = "and"):
        
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


        return self._state.data_model_transform(SubsetConceptualDataModelOnRestrictions(restrictions,
                                                                                        only_concepts_with_properties=only_concepts_with_properties,
                                                                                        include_dangling_properties=include_dangling_properties,
                                                                                        include_ancestors=include_ancestors,
                                                                                        include_different_space=include_different_space,
                                                                                        operation=operation))