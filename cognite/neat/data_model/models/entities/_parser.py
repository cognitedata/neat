def parse_entity(entity_string: str) -> tuple[str, str, dict[str, str]]:
    """Parse an entity string into its prefix, suffix, and properties.

    Args:
        entity_string (str): The entity string to parse. It can be in the format "prefix:suffix(prop1=val1,prop2=val2)"
        or "suffix(prop1=val1,prop2=val2)" or just "suffix".

    Returns:
        tuple[str, str, dict[str, str]]: A tuple containing the prefix (or an empty string if not present),
            the suffix, and a dictionary of properties.
    """

    raise NotImplementedError()
