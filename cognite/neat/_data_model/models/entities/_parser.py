import re
from dataclasses import dataclass
from typing import Literal

SPECIAL_CHARACTERS = ":()=,"


@dataclass
class ParsedEntity:
    """Represents a parsed entity string."""

    prefix: str
    suffix: str
    properties: dict[str, str]

    def __str__(self) -> str:
        props_str = ""
        if self.properties:
            joined = ",".join(f"{k}={v}" for k, v in sorted(self.properties.items(), key=lambda x: x[0]))
            props_str = f"({joined})"
        if self.prefix:
            return f"{self.prefix}:{self.suffix}{props_str}"
        return f"{self.suffix}{props_str}"

    def __hash__(self) -> int:
        return hash(str(self))


class _EntityParser:
    """A parser for entity strings in the format 'prefix:suffix(prop1=val1,prop2=val2)'."""

    def __init__(self, entity_string: str):
        """Initialize the parser with the entity string to parse.

        Args:
            entity_string: The entity string to parse.
        """
        self.entity_string = entity_string.strip() if entity_string else ""
        self.pos = 0
        self.length = len(self.entity_string)

    def peek(self) -> str:
        """Peek at current character without advancing position."""
        if self.pos >= self.length:
            return ""
        return self.entity_string[self.pos]

    def advance(self) -> str:
        """Get current character and advance position."""
        if self.pos >= self.length:
            return ""
        char = self.entity_string[self.pos]
        self.pos += 1
        return char

    def skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.pos < self.length and self.entity_string[self.pos].isspace():
            self.pos += 1

    def parse_identifier(self) -> str:
        """Parse an identifier (letters, numbers, underscores, etc.)."""
        start = self.pos
        while self.pos < self.length and self.entity_string[self.pos] not in SPECIAL_CHARACTERS:
            self.pos += 1
        return self.entity_string[start : self.pos].strip()

    def parse_property_value(self) -> str:
        """Parse a property value, handling nested parentheses."""
        start = self.pos
        paren_depth = 0

        while self.pos < self.length:
            char = self.entity_string[self.pos]
            if char == "(":
                paren_depth += 1
            elif char == ")":
                if paren_depth == 0:
                    # This is the closing paren of the properties section
                    break
                paren_depth -= 1
            elif char == "," and paren_depth == 0:
                # This is a property separator, not part of the value
                break
            self.pos += 1

        return self.entity_string[start : self.pos].strip()

    def parse_properties(self) -> dict[str, str]:
        """Parse properties within parentheses."""
        properties = {}

        # Skip opening parenthesis
        if self.peek() == "(":
            self.advance()
        else:
            raise ValueError("expected `(`")

        self.skip_whitespace()

        while self.pos < self.length and self.peek() != ")":
            # Parse property name
            self.skip_whitespace()
            if self.peek() == ")":
                break

            prop_name = self.parse_identifier()
            if not prop_name:
                raise ValueError(f"Expected property name at position {self.pos}. Got {self.peek()!r}")
            self.skip_whitespace()

            # Expect '='
            if self.peek() != "=":
                raise ValueError(
                    f"Expected '=' after property name '{prop_name}' at position {self.pos}. Got {self.peek()!r}"
                )
            self.advance()  # consume '='

            self.skip_whitespace()

            # Parse property value (handles complex values)
            prop_value = self.parse_property_value()

            properties[prop_name] = prop_value

            self.skip_whitespace()

            # Check for comma or end
            if self.peek() == ",":
                self.advance()  # consume ','

        # Check if we reached the end without finding a closing parenthesis
        if self.pos >= self.length:
            raise ValueError(f"Expected ')' to close properties at position {self.length}")

        # Skip closing parenthesis
        if self.peek() == ")":
            self.advance()

        return properties

    def parse(self) -> ParsedEntity:
        """Parse the entity string and return prefix, suffix, and properties.

        Returns:
            A `ParsedEntity` object containing the parsed components of the entity string.
        """
        if not self.entity_string:
            return ParsedEntity(prefix="", suffix="", properties={})
        if self.entity_string.strip() == ":":
            raise ValueError("Expected identifier at position 0")

        # Parse the main identifier (could be prefix:suffix or just suffix)
        main_id = self.parse_identifier()

        # Check if there's a colon (indicating prefix:suffix)
        prefix = ""
        suffix = ""

        if self.peek() == ":":
            self.advance()  # consume ':'
            prefix = main_id
            suffix = self.parse_identifier()
            if not suffix:
                raise ValueError(f"Expected identifier after ':' at position {self.pos}")
        else:
            suffix = main_id

        # Check if there are properties
        self.skip_whitespace()
        properties = {}
        if self.peek() == "(":
            properties = self.parse_properties()

        # Check for unexpected trailing characters
        self.skip_whitespace()
        if self.pos < self.length:
            raise ValueError(f"Unexpected characters after properties at position {self.pos}. Got {self.peek()!r}")

        return ParsedEntity(prefix, suffix, properties)


def parse_entity(entity_string: str) -> ParsedEntity:
    """Parse an entity string into its prefix, suffix, and properties.

    Args:
        entity_string (str): The entity string to parse. It can be in the format "prefix:suffix(prop1=val1,prop2=val2)"
        or "suffix(prop1=val1,prop2=val2)" or just "suffix".

    Returns:
        A `ParsedEntity` object containing the parsed components of the entity string.


    Raises:
        ValueError: If the entity string is malformed.

    This parser allows arbitrary characters in property values, including nested parentheses.
    Reserved characters like '=', ',', '(', and ')' are used for parsing structure and cannot appear
    unescaped in property names.

    For example, it can parse:
        - "asset:vehicle(type=car,details=(color=red,size=large))"
        - "device(sensor(model=X100,features=(wifi,bluetooth)))"
        - "location(city=New York,state=NY)"

    """
    parser = _EntityParser(entity_string)
    return parser.parse()


def parse_entities(entities_str: str, separator: Literal[","] = ",") -> list[ParsedEntity] | None:
    """Parse a comma-separated string of entities.

    Args:
        entities_str: A comma-separated string of entities.
        separator: The separator used to split entities.
        A list of `ParsedEntity` objects or None if the input string is empty.
    """
    if not entities_str.strip():
        return None
    if separator != ",":
        raise ValueError("Only ',' is supported as a separator currently.")
    # Regex to split on the separator but ignore separators within parentheses
    pattern = rf"{separator}(?![^()]*\))"
    parts = re.split(pattern, entities_str)
    return [parse_entity(part.strip()) for part in parts if part.strip()]
