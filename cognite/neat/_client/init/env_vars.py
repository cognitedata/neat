import sys
from pathlib import Path
from typing import Any, Literal, TypeAlias, get_args

from pydantic import BaseModel, ConfigDict, ValidationError

from cognite.neat._utils.repo import get_repo_root
from cognite.neat._utils.validation import humanize_validation_error

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

LoginFlow: TypeAlias = Literal["infer", "client_credentials", "interactive", "token"]
VALID_LOGIN_FLOWS = get_args(LoginFlow)
Provider: TypeAlias = Literal["entra_id", "auth0", "cdf", "other"]


class ClientEnvironmentVariables(BaseModel):
    """Configuration for environment variables used by the NEAT client."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    CDF_CLUSTER: str
    CDF_PROJECT: str
    PROVIDER: Provider = "entra_id"
    LOGIN_FLOW: LoginFlow = "infer"

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
        if self.PROVIDER == "entra_id" and self.IDP_TOKEN_URL:
            return self.IDP_TOKEN_URL.removeprefix("https://login.microsoftonline.com/").removesuffix(
                "/oauth2/v2.0/token"
            )
        raise ValueError("IDP_TENANT_ID is missing")

    @property
    def idp_token_url(self) -> str:
        if self.PROVIDER == "cdf":
            return "https://auth.cognite.com/oauth2/token"
        if self.IDP_TOKEN_URL:
            return self.IDP_TOKEN_URL
        if self.PROVIDER == "entra_id" and self.IDP_TENANT_ID:
            return f"https://login.microsoftonline.com/{self.IDP_TENANT_ID}/oauth2/v2.0/token"
        alternative = ""
        if self.PROVIDER == "entra_id":
            alternative = " or provide IDP_TENANT_ID"
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
        if self.PROVIDER == "entra_id" and self.idp_tenant_id:
            return f"https://login.microsoftonline.com/{self.idp_tenant_id}"
        alternative = ""
        if self.PROVIDER == "entra_id":
            alternative = " or provide IDP_TENANT_ID"
        raise ValueError(
            f"IDP_AUTHORITY_URL is missing. Please provide it{alternative} in the environment variables.",
        )


def get_environment_variables(env_file_name: str) -> ClientEnvironmentVariables:
    to_search: list[tuple[str, Path]] = []
    try:
        repo_root = get_repo_root()
    except RuntimeError:
        ...
    else:
        to_search.append(("repository root", repo_root))
    to_search.append(("current working directory", Path.cwd()))
    for location_desc, path in to_search:
        env_path = path / env_file_name
        if env_path.is_file():
            print(f"Found {env_file_name} in {location_desc}.")
            return _parse_env_file(env_path)
    raise FileNotFoundError(f"Could not find {env_file_name} in the repository root or current working directory.")


def _parse_env_file(env_file_path: Path) -> ClientEnvironmentVariables:
    content = env_file_path.read_text()
    variables: dict[str, Any] = {}
    for line in content.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        variables[key] = value
    return ClientEnvironmentVariables.create_humanize(variables)
