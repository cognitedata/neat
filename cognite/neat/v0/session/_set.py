from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._constants import COGNITE_MODELS
from cognite.neat.v0.core._data_model.models import PhysicalDataModel
from cognite.neat.v0.core._data_model.transformers import SetIDDMSModel
from cognite.neat.v0.core._instances.transformers import SetType
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._utils.text import humanize_collection

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class SetAPI:
    """Used to change the name of the data model from a data model id defined by neat to a user specified name."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.instances = SetInstances(state, verbose)

    def data_model_id(self, new_model_id: dm.DataModelId | tuple[str, str, str], name: str | None = None) -> IssueList:
        """Sets the data model ID of the latest verified data model. Set the data model id as a tuple of strings
        following the template (<data_model_space>, <data_model_name>, <data_model_version>).

        Args:
            new_model_id (dm.DataModelId | tuple[str, str, str]): The new data model id.
            name (str, optional): The display name of the data model. If not set, the external ID will be used
                to generate the name.

        Example:
            Set a new data model id:
            ```python
            neat.set.data_model_id(("my_data_model_space", "My_Data_Model", "v1"))
            neat.set.data_model_id(("my_data_model_space", "MyDataModel", "v1"), name="My Data Model")
            ```
        """
        if self._state.data_model_store.empty:
            raise NeatSessionError("No data model to set the data model ID.")
        data_model = self._state.data_model_store.provenance[-1].target_entity.physical
        if isinstance(data_model, PhysicalDataModel):
            if data_model.metadata.as_data_model_id() in COGNITE_MODELS:
                raise NeatSessionError(
                    "Cannot change the data model ID of a Cognite Data Model in NeatSession"
                    " due to temporarily issue with the reverse direct relation interpretation"
                )
        return self._state.data_model_transform(SetIDDMSModel(new_model_id, name))

    def client(self, client: CogniteClient) -> None:
        """Sets the client to be used in the session."""
        self._state.client = NeatClient(client)
        if self._verbose:
            print(f"Client set to {self._state.client.config.project} CDF project.")
        return None


@session_class_wrapper
class SetInstances:
    """Used to change instances"""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def type_using_property(self, current_type: str, property_type: str, drop_property: bool = True) -> None:
        """Replaces the type of all instances with the value of a property.

        Example:
            All Assets have a property `assetCategory` that we want to use as the type of all asset instances.

            ```python
            neat.set.instances.replace_type("Asset", "assetCategory")
            ```
        """
        type_uri = self._state.instances.store.queries.select.type_uri(current_type)
        property_uri = self._state.instances.store.queries.select.property_uri(property_type)

        if not type_uri:
            raise NeatValueError(f"Type {current_type} does not exist in the graph.")
        elif len(type_uri) > 1:
            raise NeatValueError(
                f"{current_type} has multiple ids found in the graph: {humanize_collection(type_uri)}."
            )

        if not property_uri:
            raise NeatValueError(f"Property {property_type} does not exist in the graph.")
        elif len(type_uri) > 1:
            raise NeatValueError(
                f"{property_type} has multiple ids found in the graph: {humanize_collection(property_uri)}."
            )

        if not self._state.instances.store.queries.select.type_with_property(type_uri[0], property_uri[0]):
            raise NeatValueError(f"Property {property_type} is not defined for type {current_type}.")

        self._state.instances.store.transform(SetType(type_uri[0], property_uri[0], drop_property))

        return None
