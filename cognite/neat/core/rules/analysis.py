from collections import defaultdict
import warnings
import pandas as pd

from cognite.neat.core.rules.models import Property, TransformationRules


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


def to_class_property_pairs(transformation_rules: TransformationRules) -> dict[str, dict[str, Property]]:
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


def get_connected_classes(transformation_rules: TransformationRules) -> set[str]:
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


def to_property_dict(rules: TransformationRules) -> dict[str, list[Property]]:
    """Convert list of properties to a dictionary of lists of properties with property_id as key."""
    property_: dict[str, list[Property]] = defaultdict(list)

    for prop in rules.properties.values():
        if not (prop.property_id and prop.property_name == "*"):
            property_[prop.property_id].append(prop)

    return property_
