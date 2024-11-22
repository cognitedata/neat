from cognite.client import CogniteClient

from cognite.neat import NeatSession


class TestRead:
    def test_read_model_referencing_core(self, cognite_client: CogniteClient) -> None:
        _ = NeatSession(cognite_client=cognite_client)
