from typing import Literal

from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat._issues import IssueList
from cognite.neat._rules.models.dms import DMSValidation
from cognite.neat._rules.transformers import (
    IncludeReferenced,
    RulesTransformer,
    ToDataProductModel,
    ToEnterpriseModel,
    ToSolutionModel,
)

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class CreateAPI:
    """
    Create new data model based on the given data.
    """

    def __init__(self, state: SessionState):
        self._state = state

    def enterprise_model(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        dummy_property: str = "GUID",
        move_connections: bool = False,
    ) -> IssueList:
        """Uses the current data model as a basis to create enterprise data model

        Args:
            data_model_id: The enterprise data model id that is being created
            org_name: Organization name to use for the views in the enterprise data model.
            dummy_property: The dummy property to use as placeholder for the views in the new data model.
            move_connections: If True, the connections will be moved to the new data model.

        !!! note "Enterprise Data Model Creation"

            Always create an enterprise data model from a Cognite Data Model as this will
            assure all the Cognite Data Fusion applications to run smoothly, such as
                - Search
                - Atlas AI
                - ...

        !!! note "Move Connections"

            If you want to move the connections to the new data model, set the move_connections
            to True. This will move the connections to the new data model and use new model
            views as the source and target views.

        """
        return self._state.rule_transform(
            ToEnterpriseModel(
                new_model_id=data_model_id,
                org_name=org_name,
                dummy_property=dummy_property,
                move_connections=move_connections,
            )
        )

    def solution_model(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        mode: Literal["read", "write"] = "read",
        dummy_property: str = "GUID",
    ) -> IssueList:
        """Uses the current data model as a basis to create solution data model

        Args:
            data_model_id: The solution data model id that is being created.
            org_name: Organization name to use for the views in the new data model.
            mode: The mode of the solution data model. Can be either "read" or "write".
            dummy_property: The dummy property to use as placeholder for the views in the new data model.

        !!! note "Solution Data Model Mode"

            The read-only solution model will only be able to read from the existing containers
            from the enterprise data model, therefore the solution data model will not have
            containers in the solution data model space. Meaning the solution data model views
            will be read-only.

            The write mode will have additional containers in the solution data model space,
            allowing in addition to reading through the solution model views, also writing to
            the containers in the solution data model space.

        """
        return self._state.rule_transform(
            ToSolutionModel(
                new_model_id=data_model_id,
                org_name=org_name,
                mode=mode,
                dummy_property=dummy_property,
            )
        )

    def data_product_model(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "",
        include: Literal["same-space", "all"] = "same-space",
    ) -> None:
        """Uses the current data model as a basis to create data product data model.

        A data product model is a data model that ONLY maps to containers and do not use implements. This is
        typically used for defining the data in a data product.

        Args:
            data_model_id: The data product data model id that is being created.
            org_name: Organization name used as prefix if the model is building on top of a Cognite Data Model.
            include: The views to include in the data product data model. Can be either "same-space" or "all".
                If you set same-space, only the properties of the views in the same space as the data model
                will be included.
        """

        view_ids, container_ids = DMSValidation(
            self._state.rule_store.last_verified_dms_rules
        ).imported_views_and_containers_ids()
        transformers: list[RulesTransformer] = []
        client = self._state.client
        if (view_ids or container_ids) and client is None:
            raise NeatSessionError(
                "No client provided. You are referencing unknown views and containers in your data model, "
                "NEAT needs a client to lookup the definitions. "
                "Please set the client in the session, NeatSession(client=client)."
            )
        elif (view_ids or container_ids) and client:
            transformers.append(IncludeReferenced(client, include_properties=True))

        transformers.append(
            ToDataProductModel(
                new_model_id=data_model_id,
                org_name=org_name,
                include=include,
            )
        )

        self._state.rule_transform(*transformers)
