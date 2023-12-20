from pydantic import BaseModel, field_validator


class CogniteClientConfig(BaseModel):
    project: str = "dev"
    client_id: str = "neat"
    base_url: str = "https://api.cognitedata.com"
    scopes: list[str] = ["project:read", "project:write"]
    timeout: int = 60
    max_workers: int = 3

    @field_validator("scopes", mode="before")
    def string_to_list(cls, value):
        return [value] if isinstance(value, str) else value


class InteractiveCogniteClient(CogniteClientConfig):
    authority_url: str
    redirect_port: int = 53_000


class ServiceCogniteClient(CogniteClientConfig):
    token_url: str = "https://login.microsoftonline.com/common/oauth2/token"
    client_secret: str = "secret"
