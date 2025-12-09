from pathlib import Path
from unittest.mock import MagicMock

from cognite.neat._v0.core._utils.auth import _from_dotenv


class TestGetCogniteClient:
    def test_from_dotenv(self) -> None:
        dotenv_path = MagicMock(spec=Path)
        dotenv_path.exists.return_value = True
        dotenv_path.read_text.return_value = """CDF_CLUSTER=my_cluster
CDF_PROJECT=my_credentials
LOGIN_FLOW=client_credentials
IDP_CLIENT_ID=my_client_id
IDP_CLIENT_SECRET=my_client_secret
IDP_TENANT_ID=my_tenant_id
CDF_CLIENT_TIMEOUT=100
    """
        env_vars = _from_dotenv(dotenv_path)
        assert env_vars.CDF_CLUSTER == "my_cluster"
        assert env_vars.CDF_PROJECT == "my_credentials"
        assert env_vars.LOGIN_FLOW == "client_credentials"
        assert env_vars.IDP_CLIENT_ID == "my_client_id"
        assert env_vars.IDP_CLIENT_SECRET == "my_client_secret"
        assert env_vars.IDP_TENANT_ID == "my_tenant_id"
        assert env_vars.CDF_CLIENT_TIMEOUT == 100
