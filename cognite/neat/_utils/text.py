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
    if "_" in string:
        # Could be a combination of snake and pascal/camel case
        parts = string.split("_")
        pascal_splits = [to_pascal(subpart) for part in parts for subpart in part.split("-") if subpart]
    elif "-" in string:
        # Could be a combination of kebab and pascal/camel case
        parts = string.split("-")
        pascal_splits = [to_pascal(subpart) for part in parts for subpart in part.split("_") if subpart]
    else:
        # Assume is pascal/camel case
        # Ensure pascal
        string = string[0].upper() + string[1:]
        pascal_splits = [string]
    string_split = []
    for part in pascal_splits:
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
