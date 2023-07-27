from cognite.client import CogniteClient
from cognite.neat.workflows.inheritance_based.graph2assets_relationships import Graph2AssetHierarchyBaseWorkflow


class Graph2AssetHierarchyNeatWorkflow(Graph2AssetHierarchyBaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client)
