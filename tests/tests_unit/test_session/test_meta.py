"""
Meta tests are that checks that the implementation of NeatSession follows the pattern
agreed upon by the team. This includes the following:
    - All parameters should be primary types (int, str, float, bool, etc.) or list/tuple of primary types.
"""

from cognite.neat import NeatSession
from cognite.neat._utils.auxiliary import get_parameters_by_method


def test_method_parameters_is_primary_types() -> None:
    neat = NeatSession()

    _ = get_parameters_by_method(neat)
    assert True


def is_allowed_type() -> bool:
    raise NotImplementedError()
