from pydantic import Field

from ._base import Resource
from ._container import ContainerRequest
from ._data_model import DataModelRequest
from ._references import NodeReference
from ._space import SpaceRequest
from ._views import ViewRequest


class RequestSchema(Resource):
    """Represents a schema for creating or updating a data model in DMS."""

    data_model: DataModelRequest
    views: list[ViewRequest] = Field(default_factory=list)
    containers: list[ContainerRequest] = Field(default_factory=list)
    spaces: list[SpaceRequest] = Field(default_factory=list)
    node_types: list[NodeReference] = Field(default_factory=list)
