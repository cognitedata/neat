from collections.abc import Iterable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cognite.client import ClientConfig, CogniteClient
from cognite.client.credentials import OAuthClientCredentials, Token

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
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
PROVIDER=cdf
IDP_CLIENT_ID=client-id-123
IDP_CLIENT_SECRET=secret-xyz
""",
        ClientConfig(
            client_name=CLIENT_NAME,
            project="my_project",
            base_url="https://my_cluster.cognitedata.com",
            credentials=OAuthClientCredentials(
                token_url="https://auth.cognite.com/oauth2/token",
                client_id="client-id-123",
                client_secret="secret-xyz",
                scopes=None,  # type: ignore[arg-type]
            ),
        ),
        id="Client Credentials - CDF provider",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
IDP_CLIENT_ID=client-id-123
IDP_CLIENT_SECRET=secret-xyz
IDP_TOKEN_URL=https://custom.idp.com/oauth2/token
IDP_SCOPES=USERS_READ,DATA_READ
IDP_AUDIENCE=https://custom.audience.com/resource
IDP_AUTHORITY_URL=https://custom.idp.com/authorize
""",
        ClientConfig(
            client_name=CLIENT_NAME,
            project="my_project",
            base_url="https://my_cluster.cognitedata.com",
            credentials=OAuthClientCredentials(
                token_url="https://custom.idp.com/oauth2/token",
                client_id="client-id-123",
                client_secret="secret-xyz",
                scopes=["USERS_READ", "DATA_READ"],
            ),
        ),
        id="Client Credentials - explicit token URL",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
PROVIDER=auth0
IDP_CLIENT_ID=client-id-123
IDP_CLIENT_SECRET=secret-xyz
IDP_TOKEN_URL=https://auth0.idp.com/oauth2/token
""",
        ClientConfig(
            client_name=CLIENT_NAME,
            project="my_project",
            base_url="https://my_cluster.cognitedata.com",
            credentials=OAuthClientCredentials(
                token_url="https://auth0.idp.com/oauth2/token",
                client_id="client-id-123",
                client_secret="secret-xyz",
                audience="https://my_project.fusion.cognite.com/my_project",
                scopes=["IDENTITY", "user_impersonation"],
            ),
        ),
        id="Client Credentials - auth0 provider",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=token
CDF_TOKEN=my-secret-token
""",
        ClientConfig(
            client_name=CLIENT_NAME,
            project="my_project",
            base_url="https://my_cluster.cognitedata.com",
            credentials=Token("my-secret-token"),
        ),
        id="Token credentials",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=infer
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
        id="Infer - client credentials (secret provided)",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=infer
CDF_TOKEN=my-secret-token
""",
        ClientConfig(
            client_name=CLIENT_NAME,
            project="my_project",
            base_url="https://my_cluster.cognitedata.com",
            credentials=Token("my-secret-token"),
        ),
        id="Infer - token (token provided)",
    )


def get_cognite_client_interactive_test_cases() -> Iterable[tuple]:
    """Test cases for interactive login flow. These need special
    handling since initialization involves user interaction."""
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
    CDF_PROJECT=my_project
    LOGIN_FLOW=interactive
    IDP_CLIENT_ID=client-id-123
    IDP_TENANT_ID=tenant-789
    """,
        dict(
            authority_url="https://login.microsoftonline.com/tenant-789",
            client_id="client-id-123",
            scopes=["https://my_cluster.cognitedata.com/.default"],
        ),
        id="Interactive credentials",
    )

    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=infer
IDP_CLIENT_ID=client-id-123
IDP_TENANT_ID=tenant-789
""",
        dict(
            authority_url="https://login.microsoftonline.com/tenant-789",
            client_id="client-id-123",
            scopes=["https://my_cluster.cognitedata.com/.default"],
        ),
        id="Infer - interactive (only client_id provided)",
    )


def get_cognite_client_invalid_cases() -> Iterable[tuple]:
    yield pytest.param(
        """CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
""",
        "CDF_CLUSTER",
        id="Missing cluster",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
""",
        "IDP_CLIENT_ID and IDP_CLIENT_SECRET",
        id="Client Credentials - missing client ID and secret",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
IDP_CLIENT_ID=client-id-123
""",
        "IDP_CLIENT_SECRET",
        id="Client Credentials - missing client secret",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
IDP_CLIENT_SECRET=secret-xyz
""",
        "IDP_CLIENT_ID",
        id="Client Credentials - missing client ID",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
PROVIDER=entra_id
LOGIN_FLOW=client_credentials
IDP_CLIENT_ID=client-id-123
IDP_CLIENT_SECRET=secret-xyz
""",
        "IDP_TENANT_ID",
        id="Client Credentials - missing tenant ID for Entra ID provider",
    )

    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=client_credentials
PROVIDER=other
IDP_CLIENT_ID=client-id-123
IDP_CLIENT_SECRET=secret-xyz
""",
        "IDP_TOKEN_URL is missing",
        id="Client Credentials - other provider missing token URL",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=interactive
""",
        "IDP_CLIENT_ID",
        id="Interactive credentials - missing client ID",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=interactive
PROVIDER=other
IDP_CLIENT_ID=client-id-123
""",
        "IDP_AUTHORITY_URL is missing",
        id="Interactive credentials - other provider missing authority URL",
    )
    yield pytest.param(
        """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_project
LOGIN_FLOW=token
""",
        "CDF_TOKEN",
        id="Token credentials - missing token",
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

    @pytest.mark.parametrize(
        "env_file_content, expected_credentials", list(get_cognite_client_interactive_test_cases())
    )
    def test_get_cognite_client_interactive_cases(
        self, env_file_content: str, expected_credentials: dict[str, Any], tmp_path: Path
    ) -> None:
        mock_credentials = MagicMock()
        env_file = tmp_path / "test.env"
        env_file.write_text(env_file_content)
        module_str = get_cognite_client.__module__
        with (
            patch(f"{module_str}.{CogniteClient.__name__}", return_value=MagicMock()) as _,
            patch("cognite.neat._client.init.env_vars.get_repo_root", return_value=tmp_path),
            patch(
                "cognite.neat._client.init.credentials.OAuthInteractive", return_value=mock_credentials
            ) as mock_interactive,
        ):
            _ = get_cognite_client("test.env")

        mock_interactive.assert_called_once()
        actual_credentials = mock_interactive.call_args[1]
        assert actual_credentials == expected_credentials

    @pytest.mark.parametrize("env_file_content, expected_message", list(get_cognite_client_invalid_cases()))
    def test_get_cognite_client_invalid_cases(
        self, env_file_content: str, expected_message: str, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "test.env"
        env_file.write_text(env_file_content)
        module_str = get_cognite_client.__module__
        with (
            patch("cognite.neat._client.init.env_vars.get_repo_root", return_value=tmp_path),
            patch(f"{module_str}.{CogniteClient.__name__}", return_value=MagicMock()) as _,
        ):
            with pytest.raises(RuntimeError) as exc_info:
                _ = get_cognite_client("test.env")

        assert expected_message in str(exc_info.value)
