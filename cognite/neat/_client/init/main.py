from cognite.client import CogniteClient
from cognite.client.config import ClientConfig, global_config

from cognite.neat import _version

from .credentials import get_credentials
from .env_vars import ClientEnvironmentVariables, get_environment_variables

CLIENT_NAME = f"CogniteNeat:{_version.__version__}"


def get_cognite_client(env_file_name: str) -> CogniteClient:
    """Get a CogniteClient using environment variables from a .env file."

    Args:
        env_file_name: The name of the .env file to look for in the repository root / current working directory. If
        the file is found, the variables will be loaded from the file. If the file is not found, the user will
        be prompted to enter the variables and the file will be created.

    Returns:
        CogniteClient: An instance of CogniteClient configured with the loaded environment variables.
    """
    try:
        return get_cognite_client_internal(env_file_name)
    except Exception as e:
        raise RuntimeError(f"Failed to create client ❌: {e!s}") from None


def get_cognite_client_internal(env_file_name: str) -> CogniteClient:
    # This function raises exceptions on failure
    if not env_file_name.endswith(".env"):
        raise ValueError(f"env_file_name must end with '.env'. Got: {env_file_name!r}")
    global_config.disable_pypi_version_check = True
    global_config.silence_feature_preview_warnings = True
    env_vars = get_environment_variables(env_file_name)
    client_config = create_client_config_from_env_vars(env_vars)
    # Todo validate credentials by making a simple call to CDF
    #   Offer to store credentials securely if valid
    #
    return CogniteClient(client_config)


def create_client_config_from_env_vars(env_vars: ClientEnvironmentVariables) -> ClientConfig:
    return ClientConfig(
        client_name=CLIENT_NAME,
        project=env_vars.CDF_PROJECT,
        credentials=get_credentials(env_vars),
        max_workers=env_vars.CDF_MAX_WORKERS,
        timeout=env_vars.CDF_CLIENT_TIMEOUT,
        base_url=env_vars.cdf_url,
    )
