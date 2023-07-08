from pydantic import BaseModel, validator


class ClientConfig(BaseModel):
    project: str = "dev"
    client_id: str = "neat"
    client_name: str = "neat"
    base_url: str = "https://api.cognitedata.com"
    scopes: list[str] = ["project:read", "project:write"]
    timeout: int = 60
    max_workers: int = 3

    @validator("scopes", pre=True)
    def string_to_list(cls, value):
        return [value] if isinstance(value, str) else value


class InteractiveClient(ClientConfig):
    authority_url: str
    redirect_port: int = 53_000


class ServiceClient(ClientConfig):
    token_url: str = "https://login.microsoftonline.com/common/oauth2/token"
    client_secret: str = "secret"
