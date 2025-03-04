import re
import urllib.parse
from collections.abc import Collection, Set
from re import Pattern
from typing import Any

from cognite.neat._rules._constants import get_reserved_words

PREPOSITIONS = frozenset(
    {
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
    }
)


def to_camel_case(string: str) -> str:
    """Convert snake_case_name to camelCaseName.

    Args:
        string: The string to convert.
    Returns:
        camelCase of the input string.

    Examples:
        >>> to_camel_case("a_b")
        'aB'
        >>> to_camel_case("ScenarioInstance_priceForecast")
        'scenarioInstancePriceForecast'
    """
    string = re.sub(r"[^a-zA-Z0-9_]", "_", string)
    string = re.sub("_+", "_", string)
    is_all_upper = string.upper() == string
    is_first_upper = (
        len(string) >= 2 and string[:2].upper() == string[:2] and "_" not in string[:2] and not is_all_upper
    )
    return _to_camel_case(string, is_all_upper, is_first_upper)


def _to_camel_case(string, is_all_upper: bool, is_first_upper: bool):
    if "_" in string:
        pascal_splits = [
            _to_pascal_case(part, is_all_upper, is_first_upper and no == 0)
            for no, part in enumerate(string.split("_"), 0)
        ]
    else:
        # Ensure pascal
        if string:
            string = string[0].upper() + string[1:]
        pascal_splits = [string]
    cleaned: list[str] = []
    for part in pascal_splits:
        if part.upper() == part and is_all_upper:
            cleaned.append(part.capitalize())
        else:
            cleaned.append(part)

    string_split = []
    for part in cleaned:
        string_split.extend(re.findall(r"[A-Z][a-z0-9]*", part))
    if not string_split:
        string_split = [string]
    if len(string_split) == 0:
        return ""
    # The first word is a single letter, keep the original case
    if is_first_upper:
        return "".join(word for word in string_split)
    else:
        return string_split[0].casefold() + "".join(word for word in string_split[1:])


def to_pascal_case(string: str) -> str:
    """Convert string to PascalCaseName.

    Args:
        string: The string to convert.
    Returns:
        PascalCase of the input string.

    Examples:
        >>> to_pascal_case("a_b")
        'AB'
        >>> to_pascal_case('camel_case')
        'CamelCase'
    """
    return _to_pascal_case(string, string == string.upper(), True)


def _to_pascal_case(string: str, is_all_upper: bool, is_first_upper: bool) -> str:
    camel = _to_camel_case(string, is_all_upper, is_first_upper)
    return f"{camel[0].upper()}{camel[1:]}" if camel else ""


def to_snake_case(string: str) -> str:
    """
    Convert input string to snake_case

    Args:
        string: The string to convert.
    Returns:
        snake_case of the input string.

    Examples:
        >>> to_snake_case("aB")
        'a_b'
        >>> to_snake_case('CamelCase')
        'camel_case'
        >>> to_snake_case('camelCamelCase')
        'camel_camel_case'
        >>> to_snake_case('Camel2Camel2Case')
        'camel_2_camel_2_case'
        >>> to_snake_case('getHTTPResponseCode')
        'get_http_response_code'
        >>> to_snake_case('get200HTTPResponseCode')
        'get_200_http_response_code'
        >>> to_snake_case('getHTTP200ResponseCode')
        'get_http_200_response_code'
        >>> to_snake_case('HTTPResponseCode')
        'http_response_code'
        >>> to_snake_case('ResponseHTTP')
        'response_http'
        >>> to_snake_case('ResponseHTTP2')
        'response_http_2'
        >>> to_snake_case('Fun?!awesome')
        'fun_awesome'
        >>> to_snake_case('Fun?!Awesome')
        'fun_awesome'
        >>> to_snake_case('10CoolDudes')
        '10_cool_dudes'
        >>> to_snake_case('20coolDudes')
        '20_cool_dudes'
    """
    pattern = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+")
    if "_" in string:
        words = [word for section in string.split("_") for word in pattern.findall(section)]
    else:
        words = pattern.findall(string)
    return "_".join(map(str.lower, words))


def to_words(string: str) -> str:
    """Converts snake_case camelCase or PascalCase to words."""
    return to_snake_case(string).replace("_", " ")


def title(text: str, skip_words: Set[str] = PREPOSITIONS) -> str:
    """Converts text to title case, skipping prepositions."""
    words = (word.lower() for word in text.split())
    titled_words = (word.capitalize() if word not in skip_words else word for word in words)
    return " ".join(titled_words)


def sentence_or_string_to_camel(string: str) -> str:
    # Could be a combination of kebab and pascal/camel case
    if " " in string:
        parts = string.split(" ")
        try:
            return parts[0].casefold() + "".join(word.capitalize() for word in parts[1:])
        except IndexError:
            return ""
    else:
        return to_camel_case(string)


def replace_non_alphanumeric_with_underscore(text: str) -> str:
    return re.sub(r"\W+", "_", text)


def humanize_collection(collection: Collection[Any], /, *, sort: bool = True) -> str:
    if not collection:
        return ""
    elif len(collection) == 1:
        return str(next(iter(collection)))

    strings = (str(item) for item in collection)
    if sort:
        sequence = sorted(strings)
    else:
        sequence = list(strings)

    return f"{', '.join(sequence[:-1])} and {sequence[-1]}"


class NamingStandardization:
    _letter_number_underscore = re.compile(r"[^a-zA-Z0-9_]+")
    _letter_number_underscore_hyphen = re.compile(r"[^a-zA-Z0-9_-]+")
    _multi_underscore_pattern = re.compile(r"_+")
    _start_letter_pattern = re.compile(r"^[a-zA-Z]")

    @classmethod
    def standardize_class_str(cls, raw: str) -> str:
        clean = cls._clean_string(raw)
        if not cls._start_letter_pattern.match(clean):
            # Underscore ensure that 'Class' it treated as a separate word
            # in the to_pascale function
            clean = f"Class_{clean}"
        return to_pascal_case(clean)

    @classmethod
    def standardize_property_str(cls, raw: str) -> str:
        clean = cls._clean_string(raw)
        if not cls._start_letter_pattern.match(clean):
            # Underscore ensure that 'property' it treated as a separate word
            # in the to_camel function
            clean = f"property_{clean}"
        return to_camel_case(clean)

    @classmethod
    def standardize_space_str(cls, raw: str) -> str:
        clean = cls._clean_string(raw, cls._letter_number_underscore_hyphen)
        if not cls._start_letter_pattern.match(clean):
            clean = f"sp_{clean}"
        if clean in set(get_reserved_words("space")):
            clean = f"my_{clean}"
        if len(clean) > 43:
            clean = clean[:43]
        if not (clean[-1].isalnum()) and len(clean) == 43:
            clean = f"{clean[:-1]}x"
        elif not clean[-1].isalnum():
            clean = f"{clean}x"
        if not clean:
            raise ValueError("Space name must contain at least one letter.")
        return to_snake_case(clean)

    @classmethod
    def _clean_string(cls, raw: str, clean_pattern: Pattern[str] = _letter_number_underscore) -> str:
        raw = urllib.parse.unquote(raw)
        raw = clean_pattern.sub("_", raw)
        return cls._multi_underscore_pattern.sub("_", raw)
