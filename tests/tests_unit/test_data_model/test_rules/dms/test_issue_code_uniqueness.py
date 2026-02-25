from collections import Counter

from cognite.neat._data_model.rules.dms import DataModelRule
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from tests.tests_unit.test_data_model.test_rules.dms.test_alpha_validator import NEAT_TEST_BASE_CODE


def test_validator_code_uniqueness() -> None:
    """Test that all DataModelValidator subclasses have unique codes."""

    # Recursively get all subclasses
    all_validators: list[type[DataModelRule]] = get_concrete_subclasses(DataModelRule)

    # Get all codes
    # The NEAT_TEST_BASE_CODE is used in testing and may be duplicated, as we execute the same test
    # multiple times with different data.
    codes = [validator.code for validator in all_validators if validator.code.startswith(NEAT_TEST_BASE_CODE)]

    # Check for duplicates
    duplicates = [code for code, count in Counter(codes).items() if count > 1]

    assert len(codes) == len(set(codes)), f"Duplicate validator codes found: {set(duplicates)}"
    assert len(codes) > 0, "No validator codes found - ensure validators have _code attribute"
