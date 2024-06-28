import os
import subprocess
from contextlib import suppress
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, TypeAlias, get_args

from cognite.client import CogniteClient
from cognite.client.credentials import CredentialProvider, OAuthClientCredentials, OAuthInteractive, Token

from cognite.neat import _version
from cognite.neat.utils.auxiliary import local_import

__all__ = ["get_cognite_client"]

_LOGIN_FLOW: TypeAlias = Literal["infer", "client_credentials", "interactive", "token"]
_VALID_LOGIN_FLOWS = get_args(_LOGIN_FLOW)
_CLIENT_NAME = f"CogniteNeat:{_version.__version__}"


def get_cognite_client(env_file_name: str = ".env") -> CogniteClient:
    if not env_file_name.endswith(".env"):
        raise ValueError("env_file_name must end with '.env'")
    with suppress(KeyError):
        variables = _EnvironmentVariables.create_from_environ()
        return variables.get_client()

    repo_root = _repo_root()
    if repo_root:
        with suppress(KeyError, FileNotFoundError, TypeError):
            variables = _from_dotenv(repo_root / env_file_name)
            client = variables.get_client()
            print("Found .env file in repository root. Loaded variables from .env file.")
            return client
    variables = _prompt_user()
    if repo_root and _env_in_gitignore(repo_root, env_file_name):
        local_import("rich", "jupyter")
        from rich.prompt import Prompt

        env_file = repo_root / env_file_name
        answer = Prompt.ask(
            "Do you store the variables in an .env file in the repository root for easy reuse?", choices=["y", "n"]
        )
        if env_file.exists():
            answer = Prompt.ask(f"{env_file} already exists. Overwrite?", choices=["y", "n"])
        if answer == "y":
            env_file.write_text(variables.create_env_file())
            print("Created .env file in repository root.")

    return variables.get_client()


@dataclass
class _EnvironmentVariables:
    CDF_CLUSTER: str
    CDF_PROJECT: str
    LOGIN_FLOW: _LOGIN_FLOW = "infer"
    IDP_CLIENT_ID: str | None = None
    IDP_CLIENT_SECRET: str | None = None
    TOKEN: str | None = None

    IDP_TENANT_ID: str | None = None
    IDP_TOKEN_URL: str | None = None

    CDF_URL: str | None = None
    IDP_AUDIENCE: str | None = None
    IDP_SCOPES: str | None = None
    IDP_AUTHORITY_URL: str | None = None

    def __post_init__(self):
        if self.LOGIN_FLOW.lower() not in _VALID_LOGIN_FLOWS:
            raise ValueError(f"LOGIN_FLOW must be one of {_VALID_LOGIN_FLOWS}")

    @property
    def cdf_url(self) -> str:
        return self.CDF_URL or f"https://{self.CDF_CLUSTER}.cognitedata.com"

    @property
    def idp_token_url(self) -> str:
        if self.IDP_TOKEN_URL:
            return self.IDP_TOKEN_URL
        if not self.IDP_TENANT_ID:
            raise KeyError("IDP_TENANT_ID or IDP_TOKEN_URL must be set in the environment.")
        return f"https://login.microsoftonline.com/{self.IDP_TENANT_ID}/oauth2/v2.0/token"

    @property
    def idp_audience(self) -> str:
        return self.IDP_AUDIENCE or f"https://{self.CDF_CLUSTER}.cognitedata.com"

    @property
    def idp_scopes(self) -> list[str]:
        if self.IDP_SCOPES:
            return self.IDP_SCOPES.split(",")
        return [f"https://{self.CDF_CLUSTER}.cognitedata.com/.default"]

    @property
    def idp_authority_url(self) -> str:
        if self.IDP_AUTHORITY_URL:
            return self.IDP_AUTHORITY_URL
        if not self.IDP_TENANT_ID:
            raise KeyError("IDP_TENANT_ID or IDP_AUTHORITY_URL must be set in the environment.")
        return f"https://login.microsoftonline.com/{self.IDP_TENANT_ID}"

    @classmethod
    def create_from_environ(cls) -> "_EnvironmentVariables":
        if "CDF_CLUSTER" not in os.environ or "CDF_PROJECT" not in os.environ:
            raise KeyError("CDF_CLUSTER and CDF_PROJECT must be set in the environment.", "CDF_CLUSTER", "CDF_PROJECT")

        return cls(
            CDF_CLUSTER=os.environ["CDF_CLUSTER"],
            CDF_PROJECT=os.environ["CDF_PROJECT"],
            LOGIN_FLOW=os.environ.get("LOGIN_FLOW", "infer"),  # type: ignore[arg-type]
            IDP_CLIENT_ID=os.environ.get("IDP_CLIENT_ID"),
            IDP_CLIENT_SECRET=os.environ.get("IDP_CLIENT_SECRET"),
            TOKEN=os.environ.get("TOKEN"),
            CDF_URL=os.environ.get("CDF_URL"),
            IDP_TOKEN_URL=os.environ.get("IDP_TOKEN_URL"),
            IDP_TENANT_ID=os.environ.get("IDP_TENANT_ID"),
            IDP_AUDIENCE=os.environ.get("IDP_AUDIENCE"),
            IDP_SCOPES=os.environ.get("IDP_SCOPES"),
            IDP_AUTHORITY_URL=os.environ.get("IDP_AUTHORITY_URL"),
        )

    def get_credentials(self) -> CredentialProvider:
        method_by_flow = {
            "client_credentials": self.get_oauth_client_credentials,
            "interactive": self.get_oauth_interactive,
            "token": self.get_token,
        }
        if self.LOGIN_FLOW in method_by_flow:
            return method_by_flow[self.LOGIN_FLOW]()
        key_options: list[tuple[str, ...]] = []
        for method in method_by_flow.values():
            try:
                return method()
            except KeyError as e:
                key_options += e.args[1:]
        raise KeyError(
            f"LOGIN_FLOW={self.LOGIN_FLOW} requires one of the following environment set variables to be set.",
            *key_options,
        )

    def get_oauth_client_credentials(self) -> OAuthClientCredentials:
        if not self.IDP_CLIENT_ID or not self.IDP_CLIENT_SECRET:
            raise KeyError(
                "IDP_CLIENT_ID and IDP_CLIENT_SECRET must be set in the environment.",
                "IDP_CLIENT_ID",
                "IDP_CLIENT_SECRET",
            )
        return OAuthClientCredentials(
            client_id=self.IDP_CLIENT_ID,
            client_secret=self.IDP_CLIENT_SECRET,
            token_url=self.idp_token_url,
            audience=self.idp_audience,
            scopes=self.idp_scopes,
        )

    def get_oauth_interactive(self) -> OAuthInteractive:
        if not self.IDP_CLIENT_ID:
            raise KeyError("IDP_CLIENT_ID must be set in the environment.", "IDP_CLIENT_ID")
        return OAuthInteractive(
            client_id=self.IDP_CLIENT_ID,
            authority_url=self.idp_authority_url,
            redirect_port=53_000,
            scopes=self.idp_scopes,
        )

    def get_token(self) -> Token:
        if not self.TOKEN:
            raise KeyError("TOKEN must be set in the environment", "TOKEN")
        return Token(self.TOKEN)

    def get_client(self) -> CogniteClient:
        return CogniteClient.default(
            self.CDF_PROJECT, self.CDF_CLUSTER, credentials=self.get_credentials(), client_name=_CLIENT_NAME
        )

    def create_env_file(self) -> str:
        lines: list[str] = []
        first_optional = True
        for field in fields(self):
            is_optional = hasattr(self, field.name.lower())
            if is_optional and first_optional:
                lines.append(
                    "# The below variables are the defaults, they are automatically " "constructed unless they are set."
                )
                first_optional = False
            name = field.name.lower() if is_optional else field.name
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, list):
                    value = ",".join(value)
                lines.append(f"{field.name}={value}")
        return "\n".join(lines)


def _from_dotenv(evn_file: Path) -> _EnvironmentVariables:
    if not evn_file.exists():
        raise FileNotFoundError(f"{evn_file} does not exist.")
    content = evn_file.read_text()
    valid_variables = {f.name for f in fields(_EnvironmentVariables)}
    variables: dict[str, str] = {}
    for line in content.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in valid_variables:
            variables[key] = value
    return _EnvironmentVariables(**variables)  # type: ignore[arg-type]


def _prompt_user() -> _EnvironmentVariables:
    local_import("rich", "jupyter")
    from rich.prompt import Prompt

    try:
        variables = _EnvironmentVariables.create_from_environ()
        continue_ = Prompt.ask(
            f"Use environment variables for CDF Cluster '{variables.CDF_CLUSTER}' "
            f"and Project '{variables.CDF_PROJECT}'? [y/n]",
            choices=["y", "n"],
            default="y",
        )
        if continue_ == "n":
            variables = _prompt_cluster_and_project()
    except KeyError:
        variables = _prompt_cluster_and_project()

    login_flow = Prompt.ask("Login flow", choices=[f for f in _VALID_LOGIN_FLOWS if f != "infer"])
    variables.LOGIN_FLOW = login_flow  # type: ignore[assignment]
    if login_flow == "token":
        token = Prompt.ask("Enter token")
        variables.TOKEN = token
        return variables

    variables.IDP_CLIENT_ID = Prompt.ask("Enter IDP Client ID")
    if login_flow == "client_credentials":
        variables.IDP_CLIENT_SECRET = Prompt.ask("Enter IDP Client Secret", password=True)
        tenant_id = Prompt.ask("Enter IDP_TENANT_ID (leave empty to enter IDP_TOKEN_URL instead)")
        if tenant_id:
            variables.IDP_TENANT_ID = tenant_id
        else:
            token_url = Prompt.ask("Enter IDP_TOKEN_URL")
            variables.IDP_TOKEN_URL = token_url
        optional = ["IDP_AUDIENCE", "IDP_SCOPES"]
    else:  # login_flow == "interactive"
        tenant_id = Prompt.ask("Enter IDP_TENANT_ID (leave empty to enter IDP_AUTHORITY_URL instead)")
        if tenant_id:
            variables.IDP_TENANT_ID = tenant_id
        else:
            variables.IDP_AUTHORITY_URL = Prompt.ask("Enter IDP_TOKEN_URL")
        optional = ["IDP_SCOPES"]

    defaults = "".join(f"\n - {name}: {getattr(variables, name.lower())}" for name in optional)
    use_defaults = Prompt.ask(
        f"Use default values for the following variables?{defaults}", choices=["y", "n"], default="y"
    )
    if use_defaults:
        return variables
    for name in optional:
        value = Prompt.ask(f"Enter {name}")
        setattr(variables, name, value)
    return variables


def _prompt_cluster_and_project() -> _EnvironmentVariables:
    from rich.prompt import Prompt

    cluster = Prompt.ask("Enter CDF Cluster (example 'greenfield', 'bluefield', 'westeurope-1)")
    project = Prompt.ask("Enter CDF Project")
    return _EnvironmentVariables(cluster, project)


def _is_notebook() -> bool:
    try:
        shell = get_ipython().__class__.__name__  # type: ignore[name-defined]
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter


def _repo_root() -> Path | None:
    with suppress(Exception):
        result = subprocess.run("git rev-parse --show-toplevel".split(), stdout=subprocess.PIPE)
        return Path(result.stdout.decode().strip())
    return None


def _env_in_gitignore(repo_root: Path, env_file_name: str) -> bool:
    ignore_file = repo_root / ".gitignore"
    if not ignore_file.exists():
        return False
    else:
        ignored = {line.strip() for line in ignore_file.read_text().splitlines()}
        return env_file_name in ignored or "*.env" in ignored


if __name__ == "__main__":
    c = get_cognite_client()
    print(c.iam.token.inspect())
