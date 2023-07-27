from cognite.client import CogniteClient

from cognite.neat.workflows.inheritance_based.sme_graph_capture import SmeGraphCaptureBaseWorkflow


class SmeGraphCaptureNeatWorkflow(SmeGraphCaptureBaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client)
