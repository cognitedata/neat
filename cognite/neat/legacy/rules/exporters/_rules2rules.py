"""This module provides set of methods that perform conversion of TransformationRules
to TransformationRules for purpose of for example:

- subsetting the data model to only include desired classes and their properties
- converting classes/properties ids/names to DMS compliant format
"""

import logging
import re
import warnings
from typing import Any

from cognite.neat.legacy.rules.analysis import get_defined_classes
from cognite.neat.legacy.rules.models.rules import Rules


def subset_rules(rules: Rules, desired_classes: set, skip_validation: bool = False) -> Rules:
    """
    Subset transformation rules to only include desired classes and their properties.

    Args:
        transformation_rules: Instance of TransformationRules to subset
        desired_classes: Desired classes to include in the reduced data model
        skip_validation: Whether to skip underlying pydantic validation, by default False

    Returns:
        Instance of TransformationRules

    !!! note "Skipping Validation"
        It is fine to skip validation since we are deriving the reduced data model from data
        model (i.e. TransformationRules) which has already been validated.

    """

    defined_classes = get_defined_classes(rules)
    possible_classes = defined_classes.intersection(desired_classes)
    impossible_classes = desired_classes - possible_classes

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
        "classes": {},
        "properties": {},
        "instances": (rules.instances or []).copy(),
    }

    logging.info(f"Reducing data model to only include the following classes: {possible_classes}")
    for class_ in possible_classes:
        reduced_data_model["classes"][class_] = rules.classes[class_]

    for id_, property_definition in rules.properties.items():
        if property_definition.class_id in possible_classes:
            reduced_data_model["properties"][id_] = property_definition

    if skip_validation:
        return Rules.model_construct(**reduced_data_model)
    else:
        return Rules(**reduced_data_model)


def to_dms_compliant_rules(rules: Rules) -> Rules:
    raise NotImplementedError()


# to be used for conversion to DMS compliant format
def to_dms_name(name: str, entity_type: str, fix_casing: bool = False) -> str:
    """
    Repairs an entity name to conform to GraphQL naming convention
    >>> repair_name("wind-speed", "property")
    'windspeed'
    >>> repair_name("Wind.Speed", "property", True)
    'windSpeed'
    >>> repair_name("windSpeed", "class", True)
    'WindSpeed'
    >>> repair_name("22windSpeed", "class")
    '_22windSpeed'
    """

    # Remove any non GraphQL compliant characters
    repaired_string = re.sub(r"[^_a-zA-Z0-9]", "", name)

    # Name must start with a letter or underscore
    if repaired_string[0].isdigit():
        repaired_string = f"_{repaired_string}"

    if not fix_casing:
        return repaired_string
    # Property names must be camelCase
    if entity_type == "property" and repaired_string[0].isupper():
        return repaired_string[0].lower() + repaired_string[1:]
    # Class names must be PascalCase
    elif entity_type == "class" and repaired_string[0].islower():
        return repaired_string[0].upper() + repaired_string[1:]
    else:
        return repaired_string
