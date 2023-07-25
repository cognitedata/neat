from cognite.neat.workflows.base_workflows.sheet2cdf import Sheet2CDFBaseWorkflow
from tests.app.api.conftest import cognite_client


class Sheet2CDFNeatWorkflow(Sheet2CDFBaseWorkflow):
    def __init__(self, name: str, client: cognite_client):
        super().__init__(name, client)
