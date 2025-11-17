import pytest

from cognite.neat._exceptions import NeatException
from cognite.neat._utils.auxiliary import get_concrete_subclasses


class TestExceptions:
    @pytest.mark.parametrize("exception_class", get_concrete_subclasses(NeatException))
    def test_str_method_is_implemented(self, exception_class: type[NeatException]) -> None:
        """Test that all concrete subclasses of NeatException implement the __str__ method."""
        assert "__str__" in exception_class.__dict__, f"{exception_class.__name__} does not implement __str__ method"
