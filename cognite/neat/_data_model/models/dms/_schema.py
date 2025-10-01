from pydantic import Field

from ._base import Resource, WriteableResource
from ._container import ContainerRequest, ContainerResponse
from ._data_model import DataModelRequest, DataModelResponse
from ._references import ContainerReference, NodeReference, ViewReference
from ._space import SpaceRequest, SpaceResponse
from ._views import ViewRequest, ViewResponse


class RequestSchema(Resource):
    data_model: DataModelRequest
    views: dict[ViewReference, ViewRequest] = Field(default_factory=dict)
    containers: dict[ContainerReference, ContainerRequest] = Field(default_factory=dict)
    spaces: dict[str, SpaceRequest] = Field(default_factory=dict)
    node_types: list[NodeReference] = Field(default_factory=list)


class ResponseSchema(WriteableResource[RequestSchema]):
    data_model: DataModelResponse
    views: dict[ViewReference, ViewResponse] = Field(default_factory=dict)
    containers: dict[ContainerReference, ContainerResponse] = Field(default_factory=dict)
    spaces: dict[str, SpaceResponse] = Field(default_factory=dict)
    node_types: list[NodeReference] = Field(default_factory=list)

    def as_request(self) -> RequestSchema:
        return RequestSchema(
            data_model=self.data_model.as_request(),
            views={view_ref: view.as_request() for view_ref, view in self.views.items()},
            containers={container_ref: container.as_request() for container_ref, container in self.containers.items()},
            spaces={space_name: space.as_request() for space_name, space in self.spaces.items()},
            node_types=self.node_types,
        )
