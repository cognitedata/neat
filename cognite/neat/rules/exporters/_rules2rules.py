"""This module provides set of methods that perform conversion of TransformationRules
to TransformationRules for purpose of for example:

- subsetting the data model to only include desired classes and their properties
- converting classes/properties ids/names to DMS compliant format
"""

import logging
import warnings
from typing import Any

from pydantic import ValidationError

from cognite.neat.rules._analysis import (
    get_class_parent_pairs,
    get_classes_with_properties,
    get_defined_classes,
    to_class_dict,
)
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules._types import ClassEntity
from cognite.neat.rules.models._rules.base import SchemaCompleteness
from cognite.neat.utils.utils import get_inheritance_path


def subset_rules(rules: InformationRules, desired_classes: set[ClassEntity]) -> InformationRules:
    """
    Subset rules to only include desired classes and their properties.

    Args:
        rules: Instance of InformationRules to subset
        desired_classes: Desired classes to include in the reduced data model

    Returns:
        Instance of InformationRules

    !!! note "Inheritance"
        If desired classes contain a class that is a subclass of another class(es), the parent class(es)
        will be included in the reduced data model as well even though the parent class(es) are
        not in the desired classes set. This is to ensure that the reduced data model is
        consistent and complete.

    !!! note "Partial Reduction"
        This method does not perform checks if classes that are value types of desired classes
        properties are part of desired classes. If a class is not part of desired classes, but it
        is a value type of a property of a class that is part of desired classes, derived reduced
        rules will be marked as partial.

    !!! note "Validation"
        This method will attempt to validate the reduced rules with custom validations.
        If it fails, it will return a partial rules with a warning message, validated
        only with base Pydantic validators.
    """

    if not rules.metadata.schema_ is not SchemaCompleteness.complete:
        raise ValueError("Rules are not complete cannot perform reduction!")
    class_as_dict = to_class_dict(rules)
    class_parents_pairs = get_class_parent_pairs(rules)
    defined_classes = get_defined_classes(rules, True)

    possible_classes = defined_classes.intersection(desired_classes)
    impossible_classes = desired_classes - possible_classes

    # need to add all the parent classes of the desired classes to the possible classes
    parents: set[ClassEntity] = set()
    for class_ in possible_classes:
        parents = parents.union(
            {parent.as_class_entity() for parent in get_inheritance_path(class_, class_parents_pairs)}
        )
    possible_classes = possible_classes.union(parents)

    if not possible_classes:
        logging.error("None of the desired classes are defined in the data model!")
        raise ValueError("None of the desired classes are defined in the data model!")

    if impossible_classes:
        logging.warning(f"Could not find the following classes defined in the data model: {impossible_classes}")
        warnings.warn(
            f"Could not find the following classes defined in the data model: {impossible_classes}", stacklevel=2
        )

    reduced_data_model: dict[str, Any] = {
        "metadata": rules.metadata.model_copy(),
        "prefixes": (rules.prefixes or {}).copy(),
        "classes": [],
        "properties": [],
    }

    logging.info(f"Reducing data model to only include the following classes: {possible_classes}")
    for class_ in possible_classes:
        reduced_data_model["classes"].append(class_as_dict[class_.suffix])

    class_property_pairs = get_classes_with_properties(rules, False)

    for class_, properties in class_property_pairs.items():
        if class_ in possible_classes:
            reduced_data_model["properties"].extend(properties)

    try:
        return InformationRules(**reduced_data_model)
    except ValidationError as e:
        warnings.warn(f"Reduced data model is not complete: {e}", stacklevel=2)
        reduced_data_model["metadata"].schema_ = SchemaCompleteness.partial
        return InformationRules.model_construct(**reduced_data_model)
