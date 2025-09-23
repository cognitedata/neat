FORBIDDEN_SPACES = frozenset(["space", "cdf", "dms", "pg3", "shared", "system", "node", "edge"])

SPACE_FORMAT_PATTERN = (
    rf"^(?!({'|'.join(FORBIDDEN_SPACES)})$)"  # ban exact matches
    r"[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$"
)
