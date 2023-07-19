"""This module provides set of methods that perform conversion of TransformationRules
to TransformationRules for purpose of for example:

- subsetting the data model to only include desired classes and their properties
- converting classes/properties ids/names to DMS compliant format
"""
import logging
import warnings

from cognite.neat.core.rules.analysis import get_defined_classes
from cognite.neat.core.rules.models import TransformationRules


def subset_rules(
    transformation_rules: TransformationRules, desired_classes: set, skip_validation: bool = False
) -> TransformationRules:
    """Subset transformation rules to only include desired classes and their properties.

    Parameters
    ----------
    transformation_rules : TransformationRules
        Instance of TransformationRules to subset
    desired_classes : set
        Desired classes to include in the reduced data model
    skip_validation : bool
        To skip underlying pydantic validation, by default False

    Returns
    -------
    TransformationRules
        Instance of TransformationRules

    Notes
    -----
    It is fine to skip validation since we are deriving the reduced data model from data
    model (i.e. TransformationRules) which has already been validated.
    """

    defined_classes = get_defined_classes(transformation_rules)
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

    reduced_data_model = {
        "metadata": transformation_rules.metadata,
        "prefixes": transformation_rules.prefixes,
        "classes": {},
        "properties": {},
        "instances": transformation_rules.instances,
    }

    logging.info(f"Reducing data model to only include the following classes: {possible_classes}")
    for class_ in possible_classes:
        reduced_data_model["classes"][class_] = transformation_rules.classes[class_]

    for id_, property_definition in transformation_rules.properties.items():
        if property_definition.class_id in possible_classes:
            reduced_data_model["properties"][id_] = property_definition

    if skip_validation:
        return TransformationRules.construct(**reduced_data_model)
    else:
        return TransformationRules(**reduced_data_model)


def to_dms_compliant_rules(rules: TransformationRules) -> TransformationRules:
    ...
