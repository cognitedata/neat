from cognite.client import CogniteClient
from cognite.client.data_classes import filters


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
