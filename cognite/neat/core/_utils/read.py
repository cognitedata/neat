from typing import Any

from cognite.neat.core._issues import catch_issues
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._rules import importers
from cognite.neat.core._rules.models import InformationRules
from cognite.neat.core._utils.reader import NeatReader


def read_conceptual_model(io: Any) -> InformationRules:
    """Reads a conceptual model from a file-like object.

    Args:
        io: A file-like object containing the conceptual model data.
            Can be a file path, a file object, or a URL.

    Returns:
        InformationRules: The conceptual model as a set of information rules.

    Raises:
        NeatValueError: If the conceptual model cannot be read or is invalid.

    """
    reader = NeatReader.create(io)
    rules: InformationRules | None = None
    with catch_issues() as issues:
        input_rules = importers.ExcelImporter(reader.materialize_path()).to_rules().rules
        if input_rules:
            rules = input_rules.as_verified_rules()
    if rules is None:
        raise NeatValueError(f"Failed to read mapping file: {reader.name}. Found {len(issues)} issues")
    elif not isinstance(rules, InformationRules):
        raise NeatValueError(f"Invalid mapping. This has to be a conceptual model got {type(rules)}")
    return rules
