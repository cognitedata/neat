import re
import warnings

import pandas as pd

from cognite.neat.core.rules import _exceptions
from cognite.neat.core.rules.models import Property, TransformationRules, data_model_name_compliance_regex


def get_defined_classes(transformation_rules: TransformationRules) -> set[str]:
    """Returns classes that have been defined in the data model."""
    return {property.class_id for property in transformation_rules.properties.values()}


def get_classes_with_properties(transformation_rules: TransformationRules) -> dict[str, list[Property]]:
    """Returns classes that have been defined in the data model."""
    # TODO: Do not particularly like method name, find something more suitable
    class_property_pairs = {}

    for property_ in transformation_rules.properties.values():
        class_ = property_.class_id
        if class_ in class_property_pairs:
            class_property_pairs[class_] += [property_]
        else:
            class_property_pairs[class_] = [property_]

    return class_property_pairs


def get_class_property_pairs(transformation_rules: TransformationRules) -> dict[str, dict[str, Property]]:
    """This method will actually consider only the first definition of given property!"""
    class_property_pairs = {}

    for class_, properties in get_classes_with_properties(transformation_rules).items():
        processed_properties = {}
        for property_ in properties:
            if property_.property_id in processed_properties:
                # TODO: use appropriate Warning class from _exceptions.py
                # if missing make one !
                warnings.warn(
                    "Property has been defined more than once! Only first definition will be considered.",
                    stacklevel=2,
                )
                continue
            processed_properties[property_.property_id] = property_
        class_property_pairs[class_] = processed_properties

    return class_property_pairs


def get_class_linkage(transformation_rules: TransformationRules) -> pd.DataFrame:
    """Returns a dataframe with the class linkage of the data model."""

    class_linkage = pd.DataFrame(columns=["source_class", "target_class", "connecting_property", "max_occurrence"])
    for property_ in transformation_rules.properties.values():
        if property_.property_type == "ObjectProperty":
            new_row = pd.Series(
                {
                    "source_class": property_.class_id,
                    "target_class": property_.expected_value_type,
                    "connecting_property": property_.property_id,
                    "max_occurrence": property_.max_count,
                }
            )
            class_linkage = pd.concat([class_linkage, new_row.to_frame().T], ignore_index=True)

    class_linkage.drop_duplicates(inplace=True)

    return class_linkage


def get_connected_classes(transformation_rules: TransformationRules) -> set:
    """Return a set of classes that are connected to other classes."""
    class_linkage = get_class_linkage(transformation_rules)
    return set(class_linkage.source_class.values).union(set(class_linkage.target_class.values))


def get_disconnected_classes(transformation_rules: TransformationRules):
    """Return a set of classes that are disconnected (i.e. isolated) from other classes."""
    return get_defined_classes(transformation_rules) - get_connected_classes(transformation_rules)


def get_symmetric_pairs(transformation_rules: TransformationRules) -> set[tuple]:
    """Returns a list of pairs of symmetrically linked classes."""
    # TODO: Find better name for this method
    sym_pairs = set()

    class_linkage = get_class_linkage(transformation_rules)
    if class_linkage.empty:
        return sym_pairs

    for _, row in class_linkage.iterrows():
        source = row.source_class
        target = row.target_class
        target_targets = class_linkage[class_linkage.source_class == target].target_class.values
        if source in target_targets and (source, target) not in sym_pairs:
            sym_pairs.add((source, target))
    return sym_pairs


def get_entity_ids(transformation_rules: TransformationRules) -> set[str]:
    return set(transformation_rules.classes.keys()).union(
        {property_.property_id for property_ in transformation_rules.properties.values()}
    )

    # Methods below could as well easily go to analysis.py


def are_entity_names_dms_compliant(
    transformation_rules: TransformationRules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    """Check if data model definitions are valid."""

    flag: bool = True
    with warnings.catch_warnings(record=True) as validation_warnings:
        for class_ in transformation_rules.classes.values():
            if not re.match(data_model_name_compliance_regex, class_.class_id):
                warnings.warn(
                    _exceptions.Warning600("Class", class_.class_id, f"[Classes/Class/{class_.class_id}]").message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = True

        for row, property_ in transformation_rules.properties.items():
            if not re.match(data_model_name_compliance_regex, property_.class_id):
                warnings.warn(
                    _exceptions.Warning600("Class", property_.class_id, f"[Properties/Class/{row}]").message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = True
            if not re.match(data_model_name_compliance_regex, property_.property_id):
                warnings.warn(
                    _exceptions.Warning600("Property", property_.property_id, f"[Properties/Property/{row}]").message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = True
            if not re.match(data_model_name_compliance_regex, property_.expected_value_type):
                warnings.warn(
                    _exceptions.Warning600(
                        "Value type", property_.expected_value_type, f"[Properties/Type/{row}]"
                    ).message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )
                flag = True

    if return_report:
        return flag, _exceptions.wrangle_warnings(validation_warnings)
    else:
        return flag


def are_properties_redefined(
    transformation_rules: TransformationRules, return_report: bool = False
) -> bool | tuple[bool, list[dict]]:
    flag: bool = False
    with warnings.catch_warnings(record=True) as validation_warnings:
        analyzed_properties = {}
        for property_ in transformation_rules.properties.values():
            if property_.property_id not in analyzed_properties:
                analyzed_properties[property_.property_id] = [property_.class_id]
            elif property_.class_id in analyzed_properties[property_.property_id]:
                flag = True
                warnings.warn(
                    _exceptions.Warning601(property_.class_id, property_.property_id).message,
                    category=_exceptions.Warning600,
                    stacklevel=2,
                )

            else:
                analyzed_properties[property_.property_id].append(property_.class_id)

    if return_report:
        return flag, _exceptions.wrangle_warnings(validation_warnings)
    else:
        return flag


def property_ids_camel_case_compliant(transformation_rules) -> bool | tuple[bool, list[dict]]:
    ...


def class_id_pascal_case_compliant(transformation_rules) -> bool | tuple[bool, list[dict]]:
    ...
