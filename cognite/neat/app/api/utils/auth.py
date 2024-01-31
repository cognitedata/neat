from fastapi import Request


def extract_access_token_from_request(http_request: Request) -> str | None:
    """
    Extracts the access token from the request. The token is set by NeatHub. If the token is not set, None is returned.
    """
    if http_request:
        return http_request.headers.get("X-Neathub-Token-Access-Token")
    return None
