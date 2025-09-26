from typing import get_args

from cognite.neat._data_model.models.dms import (
    ConnectionPropertyDefinition,
    ConnectionRequestProperty,
    ConnectionResponseProperty,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection


def test_connection_properties_are_in_union() -> None:
    all_connection_property_classes = get_concrete_subclasses(
        ConnectionPropertyDefinition, exclude_direct_abc_inheritance=True
    )
    response_union = get_args(ConnectionResponseProperty.__args__[0])
    request_union = get_args(ConnectionRequestProperty.__args__[0])
    all_union_connection = set(response_union).union(set(request_union))
    missing = set(all_connection_property_classes) - set(all_union_connection)
    assert not missing, (
        f"The following ConnectionPropertyDefinition subclasses are "
        f"missing from the ConnectionPropertyDefinition union: {humanize_collection([cls.__name__ for cls in missing])}"
    )
