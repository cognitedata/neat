from cognite.client import CogniteClient
from cognite.neat.workflows.base_workflows.graph2assets_relationships import Graph2AssetHierarchyBaseWorkflow


class Graph2AssetHierarchyNeatWorkflow(Graph2AssetHierarchyBaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client)
