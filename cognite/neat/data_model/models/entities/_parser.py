def parse_entity(entity_string: str) -> tuple[str, str, dict[str, str]]:
    """Parse an entity string into its prefix, suffix, and properties.

    Args:
        entity_string (str): The entity string to parse. It can be in the format "prefix:suffix(prop1=val1,prop2=val2)"
        or "suffix(prop1=val1,prop2=val2)" or just "suffix".

    Returns:
        tuple[str, str, dict[str, str]]: A tuple containing the prefix (or an empty string if not present),
            the suffix, and a dictionary of properties.
    """
    if not entity_string:
        return "", "", {}

    # Remove leading/trailing whitespace
    entity_string = entity_string.strip()

    # Initialize parser state
    pos = 0
    length = len(entity_string)

    def peek() -> str:
        """Peek at current character without advancing position"""
        if pos >= length:
            return ""
        return entity_string[pos]

    def advance() -> str:
        """Get current character and advance position"""
        nonlocal pos
        if pos >= length:
            return ""
        char = entity_string[pos]
        pos += 1
        return char

    def skip_whitespace() -> None:
        """Skip whitespace characters"""
        nonlocal pos
        while pos < length and entity_string[pos].isspace():
            pos += 1

    def parse_identifier() -> str:
        """Parse an identifier (letters, numbers, underscores, etc.)"""
        nonlocal pos
        start = pos
        while pos < length and entity_string[pos] not in ":()=,":
            pos += 1
        return entity_string[start:pos].strip()

    def parse_properties() -> dict[str, str]:
        """Parse properties within parentheses"""
        nonlocal pos
        properties = {}

        # Skip opening parenthesis
        if peek() == "(":
            advance()

        skip_whitespace()

        while pos < length and peek() != ")":
            # Parse property name
            skip_whitespace()
            if peek() == ")":
                break

            prop_name = parse_identifier()
            skip_whitespace()

            # Expect '='
            if peek() != "=":
                raise ValueError(f"Expected '=' after property name '{prop_name}' at position {pos}")
            advance()  # consume '='

            skip_whitespace()

            # Parse property value
            prop_value = parse_identifier()

            properties[prop_name] = prop_value

            skip_whitespace()

            # Check for comma or end
            if peek() == ",":
                advance()  # consume ','
            elif peek() == ")":
                break
            else:
                # Continue to next property
                pass

        # Skip closing parenthesis
        if peek() == ")":
            advance()

        return properties

    # Start parsing
    prefix = ""
    suffix = ""
    properties = {}

    # Parse the main identifier (could be prefix:suffix or just suffix)
    main_id = parse_identifier()

    # Check if there's a colon (indicating prefix:suffix)
    if peek() == ":":
        advance()  # consume ':'
        prefix = main_id
        suffix = parse_identifier()
    else:
        suffix = main_id

    # Check if there are properties
    skip_whitespace()
    if peek() == "(":
        properties = parse_properties()

    return prefix, suffix, properties
