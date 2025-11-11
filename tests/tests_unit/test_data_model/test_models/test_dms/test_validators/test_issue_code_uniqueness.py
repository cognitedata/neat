from cognite.neat._data_model.validation.dms._base import DataModelValidator


def get_all_subclasses(cls: type) -> list[type]:
    all_subclasses = []
    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))
    return all_subclasses


def test_validator_code_uniqueness() -> None:
    """Test that all DataModelValidator subclasses have unique codes."""

    # Recursively get all subclasses
    all_validators: list[type[DataModelValidator]] = get_all_subclasses(DataModelValidator)

    # Get all codes
    codes = [validator.code for validator in all_validators]

    # Check for duplicates
    duplicates = [code for code in codes if codes.count(code) > 1]

    assert len(codes) == len(set(codes)), f"Duplicate validator codes found: {set(duplicates)}"
    assert len(codes) > 0, "No validator codes found - ensure validators have _code attribute"
