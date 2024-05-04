import warnings
from collections import defaultdict

import pandas as pd

from cognite.neat.legacy.rules.models.rdfpath import TransformationRuleType
from cognite.neat.legacy.rules.models.rules import Property, Rules


def get_defined_classes(transformation_rules: Rules) -> set[str]:
    """Returns classes that have properties defined for them in the data model.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Set of classes that have been defined in the data model
    """
    return {property.class_id for property in transformation_rules.properties.values()}


def get_classes_with_properties(transformation_rules: Rules) -> dict[str, list[Property]]:
    """Returns classes that have been defined in the data model.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Dictionary of classes with a list of properties defined for them
    """

    class_property_pairs: dict[str, list[Property]] = {}

    for property_ in transformation_rules.properties.values():
        class_ = property_.class_id
        if class_ in class_property_pairs:
            class_property_pairs[class_] += [property_]
        else:
            class_property_pairs[class_] = [property_]

    return class_property_pairs


def to_class_property_pairs(transformation_rules: Rules, only_rdfpath: bool = False) -> dict[str, dict[str, Property]]:
    """Returns a dictionary of classes with a dictionary of properties associated with them.

    Args:
        transformation_rules : Instance of TransformationRules holding the data model
        only_rdfpath : To consider only properties which have rule `rdfpath` set. Defaults False

    Returns:
        Dictionary of classes with a dictionary of properties associated with them.

    !!! note "only_rdfpath"
        If only_rdfpath is True, only properties with RuleType.rdfpath will be returned as
        a part of the dictionary of properties related to a class. Otherwise, all properties
        will be returned.
    """

    class_property_pairs = {}

    for class_, properties in get_classes_with_properties(transformation_rules).items():
        processed_properties = {}
        for property_ in properties:
            if property_.property_id in processed_properties:
                # TODO: use appropriate Warning class from _exceptions.py
                # if missing make one !
                warnings.warn(
                    "Property has been defined more than once! Only first definition will be considered.", stacklevel=2
                )
                continue

            if (only_rdfpath and property_.rule_type == TransformationRuleType.rdfpath) or not only_rdfpath:
                processed_properties[property_.property_id] = property_
        class_property_pairs[class_] = processed_properties

    return class_property_pairs


def get_class_linkage(transformation_rules: Rules) -> pd.DataFrame:
    """Returns a dataframe with the class linkage of the data model.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Dataframe with the class linkage of the data model
    """

    class_linkage = pd.DataFrame(columns=["source_class", "target_class", "connecting_property", "max_occurrence"])
    for property_ in transformation_rules.properties.values():
        if property_.property_type == "ObjectProperty":
            new_row = pd.Series(
                {
                    "source_class": property_.class_id,
                    "target_class": property_.expected_value_type.suffix,
                    "connecting_property": property_.property_id,
                    "max_occurrence": property_.max_count,
                    "linking_type": "hierarchy" if property_.resource_type_property else "relationship",
                }
            )
            class_linkage = pd.concat([class_linkage, new_row.to_frame().T], ignore_index=True)

    class_linkage.drop_duplicates(inplace=True)

    return class_linkage


def get_class_hierarchy_linkage(rules: Rules) -> pd.DataFrame:
    """Remove linkage which is not creating asset hierarchy."""
    class_linkage = get_class_linkage(rules)
    return class_linkage[class_linkage.linking_type == "hierarchy"]


def get_connected_classes(transformation_rules: Rules) -> set[str]:
    """Return a set of classes that are connected to other classes.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Set of classes that are connected to other classes
    """
    class_linkage = get_class_linkage(transformation_rules)
    return set(class_linkage.source_class.values).union(set(class_linkage.target_class.values))


def get_disconnected_classes(transformation_rules: Rules) -> set[str]:
    """Return a set of classes that are disconnected (i.e. isolated) from other classes.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Set of classes that are disconnected from other classes
    """
    return get_defined_classes(transformation_rules) - get_connected_classes(transformation_rules)


def get_symmetric_pairs(transformation_rules: Rules) -> set[tuple[str, str]]:
    """Returns a set of pairs of symmetrically linked classes.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Set of pairs of symmetrically linked classes
    """

    # TODO: Find better name for this method
    sym_pairs: set[tuple[str, str]] = set()

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


def get_entity_ids(transformation_rules: Rules) -> set[str]:
    """Returns a set of entity ids (classes and properties) defined in the data model.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Set of entity ids (classes and properties) defined in the data model
    """
    return set(transformation_rules.classes.keys()).union(
        {property_.property_id for property_ in transformation_rules.properties.values()}
    )


def to_property_dict(transformation_rules: Rules) -> dict[str, list[Property]]:
    """Convert list of properties to a dictionary of lists of properties with property_id as key.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Dictionary of lists of properties with property_id as key
    """
    property_: dict[str, list[Property]] = defaultdict(list)

    for prop in transformation_rules.properties.values():
        if not (prop.property_id and prop.property_name == "*"):
            property_[prop.property_id].append(prop)

    return property_


def get_asset_related_properties(properties: list[Property]) -> list[Property]:
    """Return properties that are used to define CDF Assets

    Args:
        properties: List of properties

    Returns:
        List of properties that are used to define CDF Assets
    """
    return [prop for prop in properties if "Asset" in prop.cdf_resource_type]


def define_class_asset_mapping(transformation_rules: Rules, class_: str) -> dict[str, list[str]]:
    """Define mapping between class and asset properties

    Args:
        transformation_rules: Instance of TransformationRules holding the data model
        class_: Class id for which mapping is to be defined

    Returns:
        Dictionary with asset properties as keys and list of class properties as values
    """
    mapping_dict: dict[str, list[str]] = {}

    class_properties = to_class_property_pairs(transformation_rules, only_rdfpath=True)[class_]

    for asset_property in get_asset_related_properties(list(class_properties.values())):
        for resource_type_property in asset_property.resource_type_property or []:
            if resource_type_property not in mapping_dict:
                mapping_dict[resource_type_property] = [asset_property.property_id]
            else:
                mapping_dict[resource_type_property] += [asset_property.property_id]

    return mapping_dict
