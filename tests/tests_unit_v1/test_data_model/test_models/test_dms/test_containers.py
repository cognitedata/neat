from typing import get_args

from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat.core._utils.text import humanize_collection
from cognite.neat.data_model.models.dms import (
    Constraint,
    ConstraintDefinition,
    DataType,
    Index,
    IndexDefinition,
    PropertyTypeDefinition,
)


def test_all_indices_are_in_union() -> None:
    all_indices = get_concrete_subclasses(IndexDefinition, exclude_direct_abc_inheritance=True)
    all_union_indices = get_args(Index.__args__[0])
    missing = set(all_indices) - set(all_union_indices)
    assert not missing, (
        f"The following IndexDefinition subclasses are "
        f"missing from the Index union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def test_all_constraints_are_in_union() -> None:
    all_constraints = get_concrete_subclasses(ConstraintDefinition, exclude_direct_abc_inheritance=True)
    all_union_constraints = get_args(Constraint.__args__[0])
    missing = set(all_constraints) - set(all_union_constraints)
    assert not missing, (
        f"The following ConstraintDefinition subclasses are "
        f"missing from the Constraint union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def test_all_property_types_are_in_union() -> None:
    all_property_types = get_concrete_subclasses(PropertyTypeDefinition, exclude_direct_abc_inheritance=True)
    all_union_property_types = get_args(DataType.__args__[0])
    missing = set(all_property_types) - set(all_union_property_types)
    assert not missing, (
        f"The following PropertyTypeDefinition subclasses are "
        f"missing from the DataType union: {humanize_collection([cls.__name__ for cls in missing])}"
    )
