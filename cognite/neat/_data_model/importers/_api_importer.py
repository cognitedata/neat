from typing import Any

from pydantic import ValidationError

from cognite.neat._client import NeatClient
from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    DataModelReference,
    RequestSchema,
    SpaceReference,
)
from cognite.neat._exceptions import CDFAPIException, DataModelImportException
from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.http_client import FailedRequestMessage
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error


class DMSAPIImporter(DMSImporter):
    """Imports DMS in the API format."""

    def __init__(self, schema: RequestSchema | dict[str, Any]) -> None:
        self._schema = schema

    def to_data_model(self) -> RequestSchema:
        if isinstance(self._schema, RequestSchema):
            return self._schema
        try:
            return RequestSchema.model_validate(self._schema)
        except ValidationError as e:
            humanized_errors = humanize_validation_error(e)
            errors = [ModelSyntaxError(message=error) for error in humanized_errors]
            raise DataModelImportException(errors) from None

    @classmethod
    def from_cdf(cls, data_model: DataModelReference, client: NeatClient) -> "DMSAPIImporter":
        """Create a DMSAPIImporter from a data model in CDF."""
        data_models = client.data_models.retrieve([data_model])
        if not data_models:
            raise CDFAPIException(messages=[FailedRequestMessage(message=f"Data model {data_model} not found in CDF.")])
        data_model = data_models[0]
        views = client.views.retrieve(data_model.views or [])
        if missing_views := set(data_model.views or []) - {view.as_reference() for view in views}:
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(
                        message=f"Views {humanize_collection(missing_views)} not found in CDF "
                        f"for data model {data_model}."
                    )
                ]
            )
        container_ids = list({container for view in views for container in view.mapped_containers})
        containers = client.containers.retrieve(container_ids)
        if missing_containers := set(container_ids) - {container.as_reference() for container in containers}:
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(
                        message=f"Containers {humanize_collection(missing_containers)} not found in CDF "
                        f"for data model {data_model}."
                    )
                ]
            )
        node_types = [nt for view in views for nt in view.node_types]
        space_ids = list(
            {data_model.space}
            | {view.space for view in views}
            | {container.space for container in containers}
            | {nt.space for nt in node_types}
        )
        spaces = client.spaces.retrieve([SpaceReference(space=space_id) for space_id in space_ids])
        if missing_spaces := set(space_ids) - {space.space for space in spaces}:
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(
                        message=f"Spaces {humanize_collection(missing_spaces)} not found in CDF "
                        f"for data model {data_model}."
                    )
                ]
            )
        return DMSAPIImporter(
            RequestSchema(
                dataModel=data_model.as_request(),
                views=[view.as_request() for view in views],
                containers=[container.as_request() for container in containers],
                nodeTypes=node_types,
                spaces=[space.as_request() for space in spaces],
            )
        )
