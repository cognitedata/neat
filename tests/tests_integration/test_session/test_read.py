from cognite.client import CogniteClient

from cognite.neat import NeatSession
from tests import data


class TestRead:
    def test_read_model_referencing_core(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)

        neat.read.yaml(data.REFERENCING_CORE, format="toolkit")

        issues = neat.verify()

        assert issues.has_errors is False
