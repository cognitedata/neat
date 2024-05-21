from cognite.client import CogniteClient
from cognite.client.data_classes import filters
from pydantic import BaseModel, field_validator


class CogniteClientConfig(BaseModel):
    project: str = "dev"
    client_id: str = "neat"
    base_url: str = "https://api.cognitedata.com"
    scopes: list[str] = ["project:read", "project:write"]
    timeout: int = 60
    max_workers: int = 3

    @field_validator("scopes", mode="before")
    def string_to_list(cls, value):
        return [value] if isinstance(value, str) else value


class InteractiveCogniteClient(CogniteClientConfig):
    authority_url: str
    redirect_port: int = 53_000


class ServiceCogniteClient(CogniteClientConfig):
    token_url: str = "https://login.microsoftonline.com/common/oauth2/token"
    client_secret: str = "secret"


def clean_space(client: CogniteClient, space: str) -> None:
    """Deletes all data in a space.

    This means all nodes, edges, views, containers, and data models located in the given space.

    Args:
        client: Connected CogniteClient
        space: The space to delete.

    """
    edges = client.data_modeling.instances.list("edge", limit=-1, filter=filters.Equals(["edge", "space"], space))
    if edges:
        instances = client.data_modeling.instances.delete(edges=edges.as_ids())
        print(f"Deleted {len(instances.edges)} edges")
    nodes = client.data_modeling.instances.list("node", limit=-1, filter=filters.Equals(["node", "space"], space))
    if nodes:
        instances = client.data_modeling.instances.delete(nodes=nodes.as_ids())
        print(f"Deleted {len(instances.nodes)} nodes")
    views = client.data_modeling.views.list(limit=-1, space=space)
    if views:
        deleted_views = client.data_modeling.views.delete(views.as_ids())
        print(f"Deleted {len(deleted_views)} views")
    containers = client.data_modeling.containers.list(limit=-1, space=space)
    if containers:
        deleted_containers = client.data_modeling.containers.delete(containers.as_ids())
        print(f"Deleted {len(deleted_containers)} containers")
    if data_models := client.data_modeling.data_models.list(limit=-1, space=space):
        deleted_data_models = client.data_modeling.data_models.delete(data_models.as_ids())
        print(f"Deleted {len(deleted_data_models)} data models")
    deleted_space = client.data_modeling.spaces.delete(space)
    print(f"Deleted space {deleted_space}")
