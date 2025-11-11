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

    def _repr_html_(self) -> str:
        """Return HTML representation of the RequestSchema."""
        html = ["<div>"]
        html.append(
            f"<h3>Data Model: {self.data_model.space}:{self.data_model.external_id}"
            f"(version={self.data_model.version})</h3>"
        )
        html.append("<table style='border-collapse: collapse;'>")
        html.append("<tr><th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Component</th>")
        html.append("<th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Count</th></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Views</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(self.views)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Containers</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(self.containers)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Spaces</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(self.spaces)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Node Types</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(self.node_types)}</td></tr>")

        html.append("</table>")
        html.append("</div>")

        return "".join(html)
