import re

# Spaces are allowed, but we replace them as well
_ILLEGAL_CHARACTERS = re.compile(r"[<>:\"/\\|?*\s]")


def to_directory_compatible(text: str) -> str:
    """Convert a string to be compatible with directory names on all platforms"""
    cleaned = _ILLEGAL_CHARACTERS.sub("_", text)
    # Replace multiple underscores with a single one
    return re.sub(r"_+", "_", cleaned)
