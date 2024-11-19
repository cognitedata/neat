"""
Meta tests are that checks that the implementation of NeatSession follows the pattern
agreed upon by the team. This includes the following:
    - All parameters should be primary types (int, str, float, bool, etc.) or list/tuple of primary types.
"""

from cognite.neat import NeatSession
from cognite.neat._utils.auxiliary import get_parameters_by_method


def test_method_parameters_is_primary_types() -> None:
    neat = NeatSession()

    parameters_by_method = get_parameters_by_method(neat)
    invalid_parameters_by_method: dict[str, dict[str, type]] = {}
    for method, parameters in parameters_by_method.items():
        invalid_parameters = {parameter: type_ for parameter, type_ in parameters.items() if not is_allowed_type(type_)}
        if invalid_parameters:
            invalid_parameters_by_method[method] = invalid_parameters
    assert not invalid_parameters_by_method, f"Non-primary parameters found: {invalid_parameters_by_method}"


def is_allowed_type(value: type) -> bool:
    raise NotImplementedError()
