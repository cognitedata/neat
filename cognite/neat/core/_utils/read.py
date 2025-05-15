from typing import Any

from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.models import ConceptualDataModel
from cognite.neat.core._issues import catch_issues
from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._utils.reader import NeatReader


def read_conceptual_model(io: Any) -> ConceptualDataModel:
    """Reads a conceptual model from a file-like object.

    Args:
        io: A file-like object containing the conceptual model data.
            Can be a file path, a file object, or a URL.

    Returns:
        ConceptualDataModel: The conceptual model as a set of information rules.

    Raises:
        NeatValueError: If the conceptual model cannot be read or is invalid.

    """
    reader = NeatReader.create(io)
    rules: ConceptualDataModel | None = None
    with catch_issues() as issues:
        input_rules = importers.ExcelImporter(reader.materialize_path()).to_data_model().unverified_data_model
        if input_rules:
            rules = input_rules.as_verified_data_model()
    if rules is None:
        raise NeatValueError(f"Failed to read mapping file: {reader.name}. Found {len(issues)} issues")
    elif not isinstance(rules, ConceptualDataModel):
        raise NeatValueError(f"Invalid mapping. This has to be a conceptual model got {type(rules)}")
    return rules
