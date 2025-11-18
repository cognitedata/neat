import re
from collections.abc import Collection
from typing import Any

NEWLINE = "\n"


def humanize_collection(collection: Collection[Any], /, *, sort: bool = True, bind_word: str = "and") -> str:
    """Convert a collection of items to a human-readable string.

    Args:
        collection: The collection of items to convert.
        sort: Whether to sort the collection before converting. Default is True.
        bind_word: The word to use to bind the last two items. Default is "and".

    Returns:
        A human-readable string of the collection.

    Examples:
        >>> humanize_collection(["b", "c", "a"])
        'a, b and c'
        >>> humanize_collection(["b", "c", "a"], sort=False)
        'b, c and a'
        >>> humanize_collection(["a", "b"])
        'a and b'
        >>> humanize_collection(["a"])
        'a'
        >>> humanize_collection([])
        ''

    """
    if not collection:
        return ""
    elif len(collection) == 1:
        return str(next(iter(collection)))

    strings = (str(item) for item in collection)
    if sort:
        sequence = sorted(strings)
    else:
        sequence = list(strings)

    return f"{', '.join(sequence[:-1])} {bind_word} {sequence[-1]}"


def title_case(s: str) -> str:
    """Convert a string to title case, handling underscores and hyphens.

    Args:
        s: The string to convert.
    Returns:
        The title-cased string.
    Examples:
        >>> title_case("hello world")
        'Hello World'
        >>> title_case("hello_world")
        'Hello World'
        >>> title_case("hello-world")
        'Hello World'
        >>> title_case("hello_world-and-universe")
        'Hello World And Universe'
        >>> title_case("HELLO WORLD")
        'Hello World'
    """
    return " ".join(word.capitalize() for word in s.replace("_", " ").replace("-", " ").split())


def split_on_capitals(text: str) -> list[str]:
    """Split a string at capital letters."""
    return re.findall(r"[A-Z][a-z]*", text)
