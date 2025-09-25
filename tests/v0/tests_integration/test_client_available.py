from cognite.client import CogniteClient


def test_cognite_client_available(cognite_client: CogniteClient) -> None:
    assert cognite_client is not None
    token = cognite_client.iam.token.inspect()
    assert token is not None
