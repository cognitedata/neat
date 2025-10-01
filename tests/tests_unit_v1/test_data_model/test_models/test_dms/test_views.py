from typing import get_args

from cognite.neat._data_model.models.dms import (
    ViewPropertyDefinition,
    ViewRequestProperty,
    ViewResponseProperty,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection


def test_all_view_properties_are_in_union() -> None:
    all_property_classes = get_concrete_subclasses(ViewPropertyDefinition, exclude_direct_abc_inheritance=True)
    response_union = get_args(ViewResponseProperty.__args__[0])
    request_union = get_args(ViewRequestProperty.__args__[0])
    all_properties_union = set(response_union).union(set(request_union))
    missing = set(all_property_classes) - set(all_properties_union)
    assert not missing, (
        f"The following ViewPropertyDefinitions subclasses are "
        f"missing from the ViewPropertyDefinitions union: {humanize_collection([cls.__name__ for cls in missing])}"
    )
