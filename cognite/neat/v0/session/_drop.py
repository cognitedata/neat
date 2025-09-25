import difflib
from collections.abc import Collection
from typing import Literal

from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import URIRef

from cognite.neat.v0.core._constants import COGNITE_MODELS
from cognite.neat.v0.core._data_model.transformers import DropModelViews
from cognite.neat.v0.core._issues import IssueList

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper

try:
    from rich import print
except ImportError:
    ...


@session_class_wrapper
class DropAPI:
    """
    Drop instances from the session. Check out `.instances()` for performing the operation.
    """

    def __init__(self, state: SessionState):
        self._state = state
        self.data_model = DropDataModelAPI(state)

    def instances(self, type: str | list[str]) -> None:
        """Drop instances from the session.

        Args:
            type: The type of instances to drop.

        Example:
            ```python
            node_type_to_drop = "Pump"
            neat.drop.instances(node_type_to_drop)
            ```
        """
        type_list = type if isinstance(type, list) else [type]

        # Temporary solution until we agree on the form of specifying named graphs
        # it will default to the default named graph
        named_graph = self._state.instances.store.default_named_graph
        uri_type_type = dict((v, k) for k, v in self._state.instances.store.queries.select.types(named_graph).items())
        selected_uri_by_type: dict[URIRef, str] = {}
        for type_item in type_list:
            if type_item not in uri_type_type:
                print(f"Type {type_item} not found.")
            selected_uri_by_type[uri_type_type[type_item]] = type_item

        result = self._state.instances.store.queries.update.drop_types(list(selected_uri_by_type.keys()))

        for type_uri, count in result.items():
            print(f"Dropped {count} instances of type {selected_uri_by_type[type_uri]}")
        return None


@session_class_wrapper
class DropDataModelAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def views(
        self,
        view_external_id: str | SequenceNotStr[str] | None = None,
        group: Literal["3D", "Annotation", "BaseViews"]
        | Collection[Literal["3D", "Annotation", "BaseViews"]]
        | None = None,
    ) -> IssueList:
        """Drops views from the data model.
        Args:
            view_external_id: The externalId of the view to drop.
            group: Only applies to CogniteCore model. This is a shorthand for dropping multiple views at once.
        """
        if sum([view_external_id is not None, group is not None]) != 1:
            raise NeatSessionError("Only one of view_external_id or group can be specified.")
        last_dms = self._state.data_model_store.last_verified_physical_data_model
        if group is not None and last_dms.metadata.as_data_model_id() not in COGNITE_MODELS:
            raise NeatSessionError("Group can only be specified for CogniteCore models.")
        if view_external_id is not None:
            existing_views = {view.view.external_id for view in last_dms.views}
            requested_views = {view_external_id} if isinstance(view_external_id, str) else set(view_external_id)
            missing_views = requested_views - existing_views
            if missing_views:
                suggestions: list[str] = []
                for view in missing_views:
                    suggestion = difflib.get_close_matches(view, existing_views, n=1)
                    if suggestion:
                        suggestions.append(f"{view} -> {suggestion[0]}")
                    else:
                        suggestions.append(f"{view} -> NOT FOUND")
                raise NeatSessionError(
                    f"{len(missing_views)} view(s) not found in the data model.\nDid you mean {', '.join(suggestions)}?"
                )
        before = len(last_dms.views)
        issues = self._state.data_model_transform(DropModelViews(view_external_id, group))
        after = len(self._state.data_model_store.last_verified_physical_data_model.views)
        print(f"Dropped {before - after} views.")
        return issues
