from collections import Counter

from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._utils.auxiliary import get_concrete_subclasses


def test_validator_code_uniqueness() -> None:
    """Test that all DataModelValidator subclasses have unique codes."""

    # Recursively get all subclasses
    all_validators: list[type[DataModelValidator]] = get_concrete_subclasses(DataModelValidator)

    # Get all codes
    codes = [validator.code for validator in all_validators]

    # Check for duplicates
    duplicates = [code for code, count in Counter(codes).items() if count > 1]

    assert len(codes) == len(set(codes)), f"Duplicate validator codes found: {set(duplicates)}"
    assert len(codes) > 0, "No validator codes found - ensure validators have _code attribute"
