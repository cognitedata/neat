from cognite.neat._data_model._shared import OnSuccess

from ._schema import RequestSchema


class SchemaDeployer(OnSuccess):
    def __init__(self, data_model: RequestSchema) -> None:
        super().__init__(data_model)
        self.data_model: RequestSchema = data_model
        self.issues: list = []

    def run(self) -> None:
        """Execute the success handler on the data model."""
        raise NotImplementedError()
