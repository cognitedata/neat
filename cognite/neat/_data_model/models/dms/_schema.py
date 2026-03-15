from pydantic import Field

from cognite.neat._utils.useful_types import BaseModelObject

from ._base import Resource
from ._container import ContainerRequest
from ._data_model import DataModelRequest
from ._references import NodeReference
from ._space import SpaceRequest
from ._views import ViewRequest


class SchemaExtra(BaseModelObject):
    governed_spaces: list[SpaceRequest] = Field(
        default_factory=list,
        description="This is an optional list of SpaceRequest objects"
        "that contains spaces that is governed by Neat. This will impact validation and deployment",
    )


class RequestSchema(Resource):
    """Represents a schema for creating or updating a data model in DMS."""

    data_model: DataModelRequest
    views: list[ViewRequest] = Field(default_factory=list)
    containers: list[ContainerRequest] = Field(default_factory=list)
    spaces: list[SpaceRequest] = Field(default_factory=list)
    node_types: list[NodeReference] = Field(default_factory=list)
    extra: SchemaExtra = Field(default_factory=SchemaExtra)

    def governed_space_set(self) -> set[str]:
        return {space.space for space in self.extra.governed_spaces} | {self.data_model.space}
