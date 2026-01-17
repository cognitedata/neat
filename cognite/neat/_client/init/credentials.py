from collections.abc import Callable

from cognite.client.credentials import CredentialProvider, OAuthClientCredentials, OAuthInteractive, Token

from cognite.neat._utils.text import humanize_collection

from .env_vars import ClientEnvironmentVariables, LoginFlow


def get_credentials(env_vars: ClientEnvironmentVariables) -> CredentialProvider:
    options: dict[LoginFlow, Callable[[ClientEnvironmentVariables], CredentialProvider]] = {
        "client_credentials": create_client_credentials,
        "interactive": create_interactive_credentials,
        "token": create_token_credentials,
    }
    return options[env_vars.LOGIN_FLOW](env_vars)


def create_client_credentials(env_vars: ClientEnvironmentVariables) -> CredentialProvider:
    missing: list[str] = []
    if not env_vars.IDP_CLIENT_ID:
        missing.append("IDP_CLIENT_ID")
    if not env_vars.IDP_CLIENT_SECRET:
        missing.append("IDP_CLIENT_SECRET")
    if env_vars.IDP_CLIENT_ID is None or env_vars.IDP_CLIENT_SECRET is None:
        raise ValueError(
            f"The following environment variables must be set for "
            f"client credentials authentication: {humanize_collection(missing)}"
        )

    if env_vars.PROVIDER == "cdf":
        return OAuthClientCredentials(
            client_id=env_vars.IDP_CLIENT_ID,
            client_secret=env_vars.IDP_CLIENT_SECRET,
            token_url=env_vars.idp_token_url,
            scopes=None,  # type: ignore[arg-type]
        )
    return OAuthClientCredentials(
        client_id=env_vars.IDP_CLIENT_ID,
        client_secret=env_vars.IDP_CLIENT_SECRET,
        token_url=env_vars.idp_token_url,
        audience=env_vars.idp_audience,
        scopes=env_vars.idp_scopes,
    )


def create_interactive_credentials(env_vars: ClientEnvironmentVariables) -> CredentialProvider:
    if not env_vars.IDP_CLIENT_ID:
        raise ValueError("IDP_CLIENT_ID environment variable must be set for interactive authentication.")
    return OAuthInteractive(
        client_id=env_vars.IDP_CLIENT_ID,
        authority_url=env_vars.idp_authority_url,
        scopes=env_vars.idp_scopes,
    )


def create_token_credentials(env_vars: ClientEnvironmentVariables) -> CredentialProvider:
    if not env_vars.CDF_TOKEN:
        raise ValueError("CDF_TOKEN environment variable must be set for token authentication.")
    return Token(env_vars.CDF_TOKEN)
