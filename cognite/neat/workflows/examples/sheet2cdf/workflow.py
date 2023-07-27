from cognite.neat.workflows.inheritance_based.sheet2cdf import Sheet2CDFBaseWorkflow
from cognite.client import CogniteClient


class Sheet2CDFNeatWorkflow(Sheet2CDFBaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client)
