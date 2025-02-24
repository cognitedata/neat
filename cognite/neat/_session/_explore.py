from typing import cast

import pandas as pd
from rdflib import URIRef

from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.text import humanize_collection

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ExploreAPI:
    """
    Explore the instances in the session.
    """

    def __init__(self, state: SessionState):
        self._state = state

    def types(self) -> pd.DataFrame:
        """List all the types of instances in the session."""
        return pd.DataFrame(self._state.instances.store.queries.types_with_instance_and_property_count())

    def properties(self) -> pd.DataFrame:
        """List all the properties of a type of instances in the session."""
        return pd.DataFrame(self._state.instances.store.queries.properties_with_count())

    def instance_with_properties(self, type: str) -> dict[str, set[str]]:
        """List all the instances of a type with their properties."""
        available_types = self._state.instances.store.queries.list_types(remove_namespace=False)
        uri_by_type = {remove_namespace_from_uri(t[0]): t[0] for t in available_types}
        if type not in uri_by_type:
            raise NeatSessionError(
                f"Type {type} not found. Available types are: {humanize_collection(uri_by_type.keys())}"
            )
        type_uri = cast(URIRef, uri_by_type[type])
        return self._state.instances.store.queries.instances_with_properties(type_uri, remove_namespace=True)
