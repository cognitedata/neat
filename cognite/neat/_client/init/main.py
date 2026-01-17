from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.config import ClientConfig, global_config

from cognite.neat import _version
from cognite.neat._utils.repo import get_repo_root

from .credentials import get_credentials
from .env_vars import ClientEnvironmentVariables, create_env_file_content, parse_env_file
from .interactive import get_interactive_flow

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

    repo_root = get_repo_root()
    if repo_root and (env_path := repo_root / env_file_name).exists():
        print(f"Found {env_file_name} in repository root.")
    elif (env_path := Path.cwd() / env_file_name).exists():
        print(f"Found {env_file_name} in current working directory.")

    if env_path.exists():
        env_vars = parse_env_file(env_path)
        client_config = create_client_config_from_env_vars(env_vars)
        return CogniteClient(client_config)

    print(f"Failed to find {env_file_name} in repository root or current working directory.")

    env_folder = repo_root if repo_root is not None else Path.cwd()
    new_env_path = env_folder / env_file_name
    message = "Could not create CogniteClient because no environment file was found."
    user = get_interactive_flow()
    if not user.create_env_file(env_file_name):
        raise RuntimeError(message)

    provider, login_flow = user.provider(), user.login_flow()
    env_content = create_env_file_content(provider, login_flow)
    new_env_path.write_text(env_content, encoding="utf-8", newline="\n")
    message += f" A template {env_file_name!r} has been created at {new_env_path!r}."
    raise RuntimeError(message)


def create_client_config_from_env_vars(env_vars: ClientEnvironmentVariables) -> ClientConfig:
    return ClientConfig(
        client_name=CLIENT_NAME,
        project=env_vars.CDF_PROJECT,
        credentials=get_credentials(env_vars),
        max_workers=env_vars.CDF_MAX_WORKERS,
        timeout=env_vars.CDF_CLIENT_TIMEOUT,
        base_url=env_vars.cdf_url,
    )
