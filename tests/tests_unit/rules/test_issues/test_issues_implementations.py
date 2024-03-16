"""In this test module we are testing that the implementation of issues
are consistently implemented."""

from cognite.neat.rules.issues import NeatValidationError, ValidationWarning


def get_all_subclasses(cls: type) -> list[type]:
    """Get all subclasses of a class."""
    return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in get_all_subclasses(s)]


def test_errors_suffix_with_error() -> None:
    """Test that all classes that inherit from NeatValidationError have the suffix 'Error'."""
    errors = get_all_subclasses(NeatValidationError)

    not_error_suffix = [error for error in errors if not error.__name__.endswith("Error")]

    assert not_error_suffix == [], f"Errors without 'Error' suffix: {not_error_suffix}"


def test_warnings_suffix_with_warning() -> None:
    """Test that all classes that inherit from ValidationWarning have the suffix 'Warning'."""
    warnings = get_all_subclasses(ValidationWarning)

    not_warning_suffix = [warning for warning in warnings if not warning.__name__.endswith("Warning")]

    assert not_warning_suffix == [], f"Warnings without 'Warning' suffix: {not_warning_suffix}"
