from collections.abc import Iterable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cognite.client import ClientConfig, CogniteClient
from cognite.client.credentials import OAuthClientCredentials

from cognite.neat._client.init.main import CLIENT_NAME, get_cognite_client


def get_cognite_client_test_cases() -> Iterable[tuple]:
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
IDP_CLIENT_ID=client-id-123
IDP_CLIENT_SECRET=secret-xyz
IDP_TENANT_ID=tenant-789
""",
        ClientConfig(
            client_name=CLIENT_NAME,
            project="my_project",
            base_url="https://my_cluster.cognitedata.com",
            credentials=OAuthClientCredentials(
                token_url="https://login.microsoftonline.com/tenant-789/oauth2/v2.0/token",
                client_id="client-id-123",
                client_secret="secret-xyz",
                scopes=["https://my_cluster.cognitedata.com/.default"],
            ),
        ),
        id="Client Credentials - minimum",
    )


class TestGetCogniteClient:
    @pytest.mark.parametrize("env_file_content, expected_config", list(get_cognite_client_test_cases()))
    def test_get_cognite_client(self, env_file_content: str, expected_config: ClientConfig, tmp_path: Path) -> None:
        mock_client = MagicMock()
        env_file = tmp_path / "test.env"
        env_file.write_text(env_file_content)
        module_str = get_cognite_client.__module__
        with (
            patch(f"{module_str}.{CogniteClient.__name__}", return_value=mock_client) as mock_cls,
            patch("cognite.neat._client.init.env_vars.get_repo_root", return_value=tmp_path),
        ):
            client = get_cognite_client("test.env")

        assert client is mock_client
        # Verify the config passed to CogniteClient
        actual_config = mock_cls.call_args[0][0]
        actual_vars = vars(actual_config)
        actual_credentials = self._clean_credential_dump(vars(actual_vars.pop("credentials")))
        expected_vars = vars(expected_config)
        expected_credentials = self._clean_credential_dump(vars(expected_vars.pop("credentials")))
        assert actual_vars == expected_vars
        assert actual_credentials == self._clean_credential_dump(expected_credentials)

    def _clean_credential_dump(self, cred_dump: dict[str, Any]) -> dict[str, Any]:
        """Remove non-deterministic fields from credential dump for comparison."""
        clean: dict[str, Any] = {}
        for key, value in cred_dump.items():
            if self._is_comparable_value(value):
                clean[key] = value
        return clean

    def _is_comparable_value(self, value: Any) -> bool:
        """Check if a value is comparable (int, float, str, bool, None, or list/tuple of these)."""
        if isinstance(value, list | tuple):
            return all(self._is_comparable_value(v) for v in value)
        return isinstance(value, int | float | str | bool | type(None))
