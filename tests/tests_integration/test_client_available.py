from cognite.client import CogniteClient


def test_cognite_client_available(cognite_client: CogniteClient) -> None:
    assert cognite_client is not None
    token = cognite_client.iam.token.inspect()
    cognite_client.post(
        "/api/v1/projects/list",
        json={"limit": 1},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    assert token is not None
