import re
from collections.abc import Collection
from typing import Any


def to_camel(string: str) -> str:
    """Convert snake_case_name to camelCaseName.

    Args:
        string: The string to convert.
    Returns:
        camelCase of the input string.

    Examples:
        >>> to_camel("a_b")
        'aB'
        >>> to_camel("ScenarioInstance_priceForecast")
        'scenarioInstancePriceForecast'
    """
    string = re.sub(r"[\s_-]", "_", string)
    string = re.sub("_+", "_", string)
    if "_" in string:
        pascal_splits = [to_pascal(part) for part in string.split("_")]
    else:
        # Ensure pascal
        string = string[0].upper() + string[1:]
        pascal_splits = [string]
    cleaned: list[str] = []
    for part in pascal_splits:
        if part.upper() == part:
            cleaned.append(part.capitalize())
        else:
            cleaned.append(part)

    string_split = []
    for part in cleaned:
        string_split.extend(re.findall(r"[A-Z][a-z0-9]*", part))
    if not string_split:
        string_split = [string]
    try:
        return string_split[0].casefold() + "".join(word.capitalize() for word in string_split[1:])
    except IndexError:
        return ""


def to_pascal(string: str) -> str:
    """Convert string to PascalCaseName.

    Args:
        string: The string to convert.
    Returns:
        PascalCase of the input string.

    Examples:
        >>> to_pascal("a_b")
        'AB'
        >>> to_pascal('camel_case')
        'CamelCase'
    """
    camel = to_camel(string)
    return f"{camel[0].upper()}{camel[1:]}" if camel else ""


def to_snake(string: str) -> str:
    """
    Convert input string to snake_case

    Args:
        string: The string to convert.
    Returns:
        snake_case of the input string.

    Examples:
        >>> to_snake("aB")
        'a_b'
        >>> to_snake('CamelCase')
        'camel_case'
        >>> to_snake('camelCamelCase')
        'camel_camel_case'
        >>> to_snake('Camel2Camel2Case')
        'camel_2_camel_2_case'
        >>> to_snake('getHTTPResponseCode')
        'get_http_response_code'
        >>> to_snake('get200HTTPResponseCode')
        'get_200_http_response_code'
        >>> to_snake('getHTTP200ResponseCode')
        'get_http_200_response_code'
        >>> to_snake('HTTPResponseCode')
        'http_response_code'
        >>> to_snake('ResponseHTTP')
        'response_http'
        >>> to_snake('ResponseHTTP2')
        'response_http_2'
        >>> to_snake('Fun?!awesome')
        'fun_awesome'
        >>> to_snake('Fun?!Awesome')
        'fun_awesome'
        >>> to_snake('10CoolDudes')
        '10_cool_dudes'
        >>> to_snake('20coolDudes')
        '20_cool_dudes'
    """
    pattern = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+")
    if "_" in string:
        words = [word for section in string.split("_") for word in pattern.findall(section)]
    else:
        words = pattern.findall(string)
    return "_".join(map(str.lower, words))


def sentence_or_string_to_camel(string: str) -> str:
    # Could be a combination of kebab and pascal/camel case
    if " " in string:
        parts = string.split(" ")
        try:
            return parts[0].casefold() + "".join(word.capitalize() for word in parts[1:])
        except IndexError:
            return ""
    else:
        return to_camel(string)


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
    _clean_pattern = re.compile(r"[^a-zA-Z0-9_]+")
    _multi_underscore_pattern = re.compile(r"_+")
    _start_letter_pattern = re.compile(r"^[a-zA-Z]")

    @classmethod
    def standardize_class_str(cls, raw: str) -> str:
        clean = cls._clean_string(raw)
        if not cls._start_letter_pattern.match(clean):
            # Underscore ensure that 'Class' it treated as a separate word
            # in the to_pascale function
            clean = f"Class_{clean}"
        return to_pascal(clean)

    @classmethod
    def standardize_property_str(cls, raw: str) -> str:
        clean = cls._clean_string(raw)
        if not cls._start_letter_pattern.match(clean):
            # Underscore ensure that 'property' it treated as a separate word
            # in the to_camel function
            clean = f"property_{clean}"
        return to_camel(clean)

    @classmethod
    def _clean_string(cls, raw: str) -> str:
        raw = cls._clean_pattern.sub("_", raw)
        return cls._multi_underscore_pattern.sub("_", raw)
