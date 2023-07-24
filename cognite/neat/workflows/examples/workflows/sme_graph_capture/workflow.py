from cognite.client import CogniteClient

from cognite.neat.workflows.base_workflows.sme_graph_capture import SmeGraphCaptureBaseWorkflow


class SmeGraphCaptureNeatWorkflow(SmeGraphCaptureBaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client)
