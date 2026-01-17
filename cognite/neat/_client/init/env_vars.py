import sys
from pathlib import Path
from typing import Any, Literal, TypeAlias, get_args

from pydantic import BaseModel, ConfigDict, ValidationError

from cognite.neat._utils.validation import humanize_validation_error

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

LoginFlow: TypeAlias = Literal["client_credentials", "interactive", "token"]
AVAILABLE_LOGIN_FLOWS: tuple[LoginFlow, ...] = get_args(LoginFlow)
Provider: TypeAlias = Literal["entra_id", "auth0", "cdf", "other"]
AVAILABLE_PROVIDERS: tuple[Provider, ...] = get_args(Provider)


class ClientEnvironmentVariables(BaseModel):
    """Configuration for environment variables used by the NEAT client."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    CDF_CLUSTER: str
    CDF_PROJECT: str
    PROVIDER: Provider = "entra_id"
    LOGIN_FLOW: LoginFlow = "client_credentials"

    IDP_CLIENT_ID: str | None = None
    IDP_CLIENT_SECRET: str | None = None
    CDF_TOKEN: str | None = None

    IDP_TENANT_ID: str | None = None
    IDP_TOKEN_URL: str | None = None

    CDF_URL: str | None = None
    IDP_AUDIENCE: str | None = None
    IDP_SCOPES: str | None = None
    IDP_AUTHORITY_URL: str | None = None
    IDP_DISCOVERY_URL: str | None = None
    CDF_MAX_WORKERS: int | None = None
    CDF_CLIENT_TIMEOUT: int | None = None
    CDF_REDIRECT_PORT: int = 53_000

    @classmethod
    def create_humanize(cls, values: dict[str, Any]) -> Self:
        try:
            return cls.model_validate(values)
        except ValidationError as e:
            errors = [humanize_validation_error(error) for error in e.errors()]
            raise ValueError("Invalid environment variable configuration:\n" + "\n - ".join(errors)) from e

    @property
    def idp_tenant_id(self) -> str:
        if self.IDP_TENANT_ID:
            return self.IDP_TENANT_ID
        # This line is technically unreachable due to the checks in idp_token_url and idp_authority_url
        raise RuntimeError("IDP_TENANT_ID is missing")

    @property
    def idp_token_url(self) -> str:
        if self.PROVIDER == "cdf":
            return "https://auth.cognite.com/oauth2/token"
        if self.IDP_TOKEN_URL:
            return self.IDP_TOKEN_URL
        if self.PROVIDER == "entra_id" and self.IDP_TENANT_ID:
            return f"https://login.microsoftonline.com/{self.IDP_TENANT_ID}/oauth2/v2.0/token"
        alternative = " or provide IDP_TENANT_ID" if self.PROVIDER == "entra_id" else ""
        raise ValueError(
            f"IDP_TOKEN_URL is missing. Please provide it{alternative} in the environment variables.",
        )

    @property
    def cdf_url(self) -> str:
        return self.CDF_URL or f"https://{self.CDF_CLUSTER}.cognitedata.com"

    @property
    def idp_audience(self) -> str:
        if self.IDP_AUDIENCE:
            return self.IDP_AUDIENCE
        if self.PROVIDER == "auth0":
            return f"https://{self.CDF_PROJECT}.fusion.cognite.com/{self.CDF_PROJECT}"
        else:
            return f"https://{self.CDF_CLUSTER}.cognitedata.com"

    @property
    def idp_scopes(self) -> list[str]:
        if self.IDP_SCOPES:
            return self.IDP_SCOPES.split(",")
        if self.PROVIDER == "auth0":
            return ["IDENTITY", "user_impersonation"]
        return [f"https://{self.CDF_CLUSTER}.cognitedata.com/.default"]

    @property
    def idp_authority_url(self) -> str:
        if self.IDP_AUTHORITY_URL:
            return self.IDP_AUTHORITY_URL
        if self.PROVIDER == "entra_id" and self.IDP_TENANT_ID:
            return f"https://login.microsoftonline.com/{self.IDP_TENANT_ID}"
        alternative = " or provide IDP_TENANT_ID" if self.PROVIDER == "entra_id" else ""
        raise ValueError(
            f"IDP_AUTHORITY_URL is missing. Please provide it{alternative} in the environment variables.",
        )


def parse_env_file(env_file_path: Path) -> ClientEnvironmentVariables:
    content = env_file_path.read_text()
    variables: dict[str, Any] = {}
    for line in content.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.strip().split("=", 1)
        variables[key] = value
    return ClientEnvironmentVariables.create_humanize(variables)


def create_env_file_content(provider: Provider, login_flow: LoginFlow) -> str:
    if login_flow == "infer":
        raise ValueError("login_flow cannot be 'infer' when creating env file content.")
    lines = [
        "# Cognite NEAT Client Environment Variables",
        "CDF_CLUSTER=<your-cdf-cluster>",
        "CDF_PROJECT=<your-cdf-project>",
        "",
    ]
    if login_flow != "token":
        lines.append(f"PROVIDER={provider}")
    lines.append(f"LOGIN_FLOW={login_flow}")
    lines.append("")
    if login_flow in ("client_credentials", "interactive"):
        lines.append("IDP_CLIENT_ID=<your-idp-client-id>")
        if login_flow == "client_credentials":
            lines.append("IDP_CLIENT_SECRET=<your-idp-client-secret>")
        if provider == "entra_id":
            lines.append("IDP_TENANT_ID=<your-idp-tenant-id>")
        if provider not in ("cdf", "entra_id"):
            lines.append("IDP_TOKEN_URL=<your-idp-token-url>")
        if provider == "other":
            lines.append("IDP_AUDIENCE=<your-idp-audience>")
            lines.append("IDP_SCOPES=<your-idp-scopes-comma-separated>")
            lines.append("IDP_AUTHORITY_URL=<your-idp-authority-url>")
    elif login_flow == "token":
        lines.append("CDF_TOKEN=<your-cdf-token>")

    return "\n".join(lines)
