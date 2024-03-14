"""To be renamed to non-private module once the migration is completed."""

import itertools
import warnings
from collections import defaultdict

import pandas as pd

from cognite.neat.rules.models._rules._types import ClassEntity, EntityTypes, ParentClassEntity
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty, InformationRules
from cognite.neat.rules.models.rdfpath import TransformationRuleType
from cognite.neat.utils.utils import get_inheritance_path


def get_class_parent_pairs(rule: InformationRules) -> dict[ClassEntity, list[ParentClassEntity]]:
    """This only returns class - parent pairs only if parent is in the same data model"""
    class_subclass_pairs: dict[ClassEntity, list[ParentClassEntity]] = {}
    for definition in rule.classes:
        class_subclass_pairs[definition.class_] = []

        if definition.parent is None:
            continue

        for parent in definition.parent:
            if parent.prefix == definition.class_.prefix:
                class_subclass_pairs[definition.class_].append(parent)
            else:
                warnings.warn(
                    f"Parent class {parent} of class {definition} is not in the same namespace, skipping !",
                    stacklevel=2,
                )

    return class_subclass_pairs


def get_classes_with_properties(
    rules: InformationRules, consider_inheritance: bool = False
) -> dict[ClassEntity, list[InformationProperty]]:
    """Returns classes that have been defined in the data model.

    Args:
        rules: Instance of InformationRules holding the data model
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Dictionary of classes with a list of properties defined for them

    !!! note "consider_inheritance"
        If consider_inheritance is True, properties from parent classes will also be considered.
        This means if a class has a parent class, and the parent class has properties defined for it,
        while we do not have any properties defined for the child class, we will still consider the
        properties from the parent class. If consider_inheritance is False, we will only consider
        properties defined for the child class, thus if no properties are defined for the child class,
        it will not be included in the returned dictionary.
    """

    class_property_pairs: dict[ClassEntity, list[InformationProperty]] = {}

    for property_ in rules.properties:
        if property_.class_ in class_property_pairs:
            class_property_pairs[property_.class_] += [property_]
        else:
            class_property_pairs[property_.class_] = [property_]

    if consider_inheritance:
        class_parent_pairs = get_class_parent_pairs(rules)
        for class_ in class_parent_pairs:
            _add_inherited_properties(class_, class_property_pairs, class_parent_pairs)

    return class_property_pairs


def _add_inherited_properties(class_, class_property_pairs, class_parent_pairs):
    inheritance_path = get_inheritance_path(class_, class_parent_pairs)
    for parent in inheritance_path:
        # ParentClassEntity -> ClassEntity to match the type of class_property_pairs
        if parent.as_class_entity() in class_property_pairs:
            for property_ in class_property_pairs[parent.as_class_entity()]:
                property_ = property_.model_copy()
                # this corresponds to importing properties from parent class
                property_.class_ = class_

                if class_ in class_property_pairs:
                    class_property_pairs[class_].append(property_)
                else:
                    class_property_pairs[class_] = [property_]


def to_class_property_pairs(
    rules: InformationRules, only_rdfpath: bool = False, consider_inheritance: bool = False
) -> dict[ClassEntity, dict[str, InformationProperty]]:
    """Returns a dictionary of classes with a dictionary of properties associated with them.

    Args:
        rules : Instance of InformationRules holding the data model
        only_rdfpath : To consider only properties which have rule `rdfpath` set. Defaults False
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Dictionary of classes with a dictionary of properties associated with them.

    !!! note "difference to get_classes_with_properties"
        This method returns a dictionary of classes with a dictionary of properties associated with them.
        While get_classes_with_properties returns a dictionary of classes with a list of properties defined for them,
        here we filter the properties based on the `only_rdfpath` parameter and only consider
        the first definition of a property if it is defined more than once.

    !!! note "only_rdfpath"
        If only_rdfpath is True, only properties with RuleType.rdfpath will be returned as
        a part of the dictionary of properties related to a class. Otherwise, all properties
        will be returned.

    !!! note "consider_inheritance"
        If consider_inheritance is True, properties from parent classes will also be considered.
        This means if a class has a parent class, and the parent class has properties defined for it,
        while we do not have any properties defined for the child class, we will still consider the
        properties from the parent class. If consider_inheritance is False, we will only consider
        properties defined for the child class, thus if no properties are defined for the child class,
        it will not be included in the returned dictionary.
    """
    # TODO: https://cognitedata.atlassian.net/jira/software/projects/NEAT/boards/893?selectedIssue=NEAT-78

    class_property_pairs = {}

    for class_, properties in get_classes_with_properties(rules, consider_inheritance).items():
        processed_properties = {}
        for property_ in properties:
            if property_.property_ in processed_properties:
                # TODO: use appropriate Warning class from _exceptions.py
                # if missing make one !
                warnings.warn(
                    f"Property {property_.property_} for {class_} has been defined more than once!"
                    " Only the first definition will be considered, skipping the rest..",
                    stacklevel=2,
                )
                continue

            if (only_rdfpath and property_.rule_type == TransformationRuleType.rdfpath) or not only_rdfpath:
                processed_properties[property_.property_] = property_
        class_property_pairs[class_] = processed_properties

    return class_property_pairs


def get_class_linkage(rules: InformationRules, consider_inheritance: bool = False) -> pd.DataFrame:
    """Returns a dataframe with the class linkage of the data model.

    Args:
        rules: Instance of InformationRules holding the data model
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Dataframe with the class linkage of the data model
    """

    class_linkage = pd.DataFrame(columns=["source_class", "target_class", "connecting_property", "max_occurrence"])

    class_property_pairs = get_classes_with_properties(rules, consider_inheritance)
    properties = list(itertools.chain.from_iterable(class_property_pairs.values()))

    for property_ in properties:
        if property_.type_ == EntityTypes.object_property:
            new_row = pd.Series(
                {
                    "source_class": property_.class_,
                    "connecting_property": property_.property_,
                    "target_class": property_.value_type,
                    "max_occurrence": property_.max_count,
                }
            )
            class_linkage = pd.concat([class_linkage, new_row.to_frame().T], ignore_index=True)

    class_linkage.drop_duplicates(inplace=True)
    class_linkage = class_linkage[["source_class", "connecting_property", "target_class", "max_occurrence"]]

    return class_linkage


def get_connected_classes(rules: InformationRules, consider_inheritance: bool = False) -> set[ClassEntity]:
    """Return a set of classes that are connected to other classes.

    Args:
        rules: Instance of InformationRules holding the data model
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Set of classes that are connected to other classes
    """
    class_linkage = get_class_linkage(rules, consider_inheritance)
    return set(class_linkage.source_class.values).union(set(class_linkage.target_class.values))


def get_defined_classes(rules: InformationRules, consider_inheritance: bool = False) -> set[ClassEntity]:
    """Returns classes that have properties defined for them in the data model.

    Args:
        rules: Instance of InformationRules holding the data model
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Set of classes that have been defined in the data model
    """
    class_property_pairs = get_classes_with_properties(rules, consider_inheritance)
    properties = list(itertools.chain.from_iterable(class_property_pairs.values()))

    return {property.class_ for property in properties}


def get_disconnected_classes(rules: InformationRules, consider_inheritance: bool = False) -> set[ClassEntity]:
    """Return a set of classes that are disconnected (i.e. isolated) from other classes.

    Args:
        rules: Instance of InformationRules holding the data model
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Set of classes that are disconnected from other classes
    """
    return get_defined_classes(rules, consider_inheritance) - get_connected_classes(rules, consider_inheritance)


def get_symmetric_pairs(
    rules: InformationRules, consider_inheritance: bool = False
) -> set[tuple[ClassEntity, ClassEntity]]:
    """Returns a set of pairs of symmetrically linked classes.

    Args:
        rules: Instance of InformationRules holding the data model
        consider_inheritance: Whether to consider inheritance or not. Defaults False

    Returns:
        Set of pairs of symmetrically linked classes
    """

    # TODO: Find better name for this method
    sym_pairs: set[tuple[ClassEntity, ClassEntity]] = set()

    class_linkage = get_class_linkage(rules, consider_inheritance)
    if class_linkage.empty:
        return sym_pairs

    for _, row in class_linkage.iterrows():
        source = row.source_class
        target = row.target_class
        target_targets = class_linkage[class_linkage.source_class == target].target_class.values
        if source in target_targets and (source, target) not in sym_pairs:
            sym_pairs.add((source, target))
    return sym_pairs


def to_property_dict(rules: InformationRules) -> dict[str, list[InformationProperty]]:
    """This is used to capture all definitions of a property in the data model."""
    property_dict: dict[str, list[InformationProperty]] = defaultdict(list)
    for definition in rules.properties:
        property_dict[definition.property_].append(definition)
    return property_dict


def to_class_dict(rules: InformationRules) -> dict[str, InformationClass]:
    """This is to simplify access to classes through dict."""
    class_dict: dict[str, InformationClass] = {}
    for definition in rules.classes:
        class_dict[definition.class_.suffix] = definition
    return class_dict
