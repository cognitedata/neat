from contextlib import contextmanager

import pytest

from cognite.neat.issues.errors import NeatError, NeatValueError


@contextmanager
def _catch_error(errors: list[NeatError]) -> None:
    try:
        yield
    except NeatError as e:
        raise RuntimeError("This should not happen") from e


class TestIssues:
    def test_raise_issue_in_contextmanager(self) -> None:
        """Test that an issue is raised in the context manager."""
        errors: list[NeatError] = []
        with pytest.raises(RuntimeError) as _:
            with _catch_error(errors):
                raise NeatValueError("Test error")

        assert len(errors) == 1
        assert str(errors[0]) == "Test error"
