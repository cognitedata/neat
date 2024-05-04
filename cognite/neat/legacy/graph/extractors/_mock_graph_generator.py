"""This module is used to generate mock graph data for purposes of testing of NEAT."""

import logging
import random
import warnings
from collections import OrderedDict

import numpy
import pandas as pd
from prometheus_client import Gauge
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.legacy.graph.models import Triple
from cognite.neat.legacy.rules.analysis import (
    get_class_linkage,
    get_classes_with_properties,
    get_defined_classes,
    get_symmetric_pairs,
)
from cognite.neat.legacy.rules.exporters._rules2rules import subset_rules
from cognite.neat.legacy.rules.models import Rules
from cognite.neat.legacy.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS
from cognite.neat.utils.utils import remove_namespace

from ._base import BaseExtractor

neat_total_processed_mock_triples = Gauge(
    "neat_total_processed_mock_triples", "Number of processed mock triples", ["state"]
)
neat_mock_triples_processing_timing = Gauge(
    "neat_mock_triples_processing_timing", "Generation of mock knowledge graph timing metrics", ["aggregation"]
)


class MockGraphGenerator(BaseExtractor):
    """
    Class used to generate mock graph data for purposes of testing of NEAT.

    Args:
        rules: Transformation rules defining the classes with their properties.
        class_count: Target class count for each class in the ontology
        stop_on_exception: To stop if exception is encountered or not, default is False
        allow_isolated_classes: To allow generation of instances for classes that are not
                                 connected to any other class, default is True
    """

    def __init__(
        self, rules: Rules, class_count: dict, stop_on_exception: bool = False, allow_isolated_classes: bool = True
    ):
        self.rules = rules
        self.class_count = class_count
        self.stop_on_exception = stop_on_exception
        self.allow_isolated_classes = allow_isolated_classes

    def extract(self) -> list[Triple]:
        """Generate mock triples based on data model defined transformation rules and desired number
        of class instances

        Returns:
            List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
        """
        return generate_triples(
            self.rules,
            self.class_count,
            stop_on_exception=self.stop_on_exception,
            allow_isolated_classes=self.allow_isolated_classes,
        )


def generate_triples(
    transformation_rules: Rules, class_count: dict, stop_on_exception: bool = False, allow_isolated_classes: bool = True
) -> list[Triple]:
    """Generate mock triples based on data model defined transformation rules and desired number
    of class instances

    Args:
        transformation_rules : Transformation rules defining the data model
        class_count: Target class count for each class in the ontology
        stop_on_exception: To stop if exception is encountered or not, default is False
        allow_isolated_classes: To allow generation of instances for classes that are not
                                 connected to any other class, default is True

    Returns:
        List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
    """

    # Figure out which classes are defined in the data model and which are not
    if transformation_rules.metadata.namespace is None:
        raise ValueError("Namespace must be defined in transformation rules!")
    namespace = transformation_rules.metadata.namespace

    defined_classes = get_defined_classes(transformation_rules)

    if non_existing_classes := set(class_count.keys()) - defined_classes:
        msg = f"Class count contains classes {non_existing_classes} for which properties are not defined in Data Model!"
        if stop_on_exception:
            logging.error(msg)
            raise ValueError(msg)
        else:
            msg += " These classes will be ignored."
            logging.warning(msg)
            warnings.warn(msg, stacklevel=2)
            for class_ in non_existing_classes:
                class_count.pop(class_)

    # Subset data model to only classes that are defined in class count
    transformation_rules = (
        subset_rules(transformation_rules, set(class_count.keys()), skip_validation=True)
        if defined_classes != set(class_count.keys())
        else transformation_rules
    )

    class_linkage = get_class_linkage(transformation_rules)

    # Remove one of symmetric pairs from class linkage to maintain proper linking
    # among instances of symmetrically linked classes
    if sym_pairs := get_symmetric_pairs(transformation_rules):
        class_linkage = _remove_higher_occurring_sym_pair(class_linkage, sym_pairs)

    # Remove any of symmetric pairs containing classes that are not present class count
    class_linkage = _remove_non_requested_sym_pairs(class_linkage, class_count)

    # Generate generation order for classes instances
    generation_order = _prettify_generation_order(_get_generation_order(class_linkage))

    # Generated simple view of data model
    class_definitions = _rules_to_dict(transformation_rules)

    # pregenerate instance ids for each remaining class
    instance_ids = {key: [URIRef(namespace[f"{key}-{i}"]) for i in range(value)] for key, value in class_count.items()}

    # create triple for each class instance defining its type
    triples: list[Triple] = []
    for class_ in class_count:
        triples += [
            (class_instance_id, RDF.type, URIRef(namespace[class_])) for class_instance_id in instance_ids[class_]
        ]

    # generate triples for connected classes
    for class_ in generation_order:
        triples += _generate_triples_per_class(
            class_, class_definitions, sym_pairs, instance_ids, namespace, stop_on_exception
        )

    # generate triples for isolated classes
    if allow_isolated_classes:
        for class_ in set(class_count.keys()) - set(generation_order):
            triples += _generate_triples_per_class(
                class_, class_definitions, sym_pairs, instance_ids, namespace, stop_on_exception
            )

    return triples


def _get_generation_order(
    class_linkage: pd.DataFrame, parent_col: str = "source_class", child_col: str = "target_class"
) -> dict:
    parent_child_list: list[list[str]] = class_linkage[[parent_col, child_col]].values.tolist()
    # Build a directed graph and a list of all names that have no parent
    graph: dict[str, set] = {name: set() for tup in parent_child_list for name in tup}
    has_parent: dict[str, bool] = {name: False for tup in parent_child_list for name in tup}
    for parent, child in parent_child_list:
        graph[parent].add(child)
        has_parent[child] = True

    # All names that have absolutely no parent:
    roots = [name for name, parents in has_parent.items() if not parents]

    return _traverse({}, graph, roots)


def _traverse(hierarchy: dict, graph: dict, names: list[str]) -> dict:
    """traverse the graph and return the hierarchy"""
    for name in names:
        hierarchy[name] = _traverse({}, graph, graph[name])
    return hierarchy


def _prettify_generation_order(generation_order: dict, depth: dict | None = None, start=-1) -> dict:
    """Prettifies generation order dictionary for easier consumption."""
    depth = depth or {}
    for key, value in generation_order.items():
        depth[key] = start + 1
        if isinstance(value, dict):
            _prettify_generation_order(value, depth, start=start + 1)
    return OrderedDict(sorted(depth.items(), key=lambda item: item[1]))


def _remove_non_hierarchy_linking(class_linkage: pd.DataFrame) -> pd.DataFrame:
    """Remove linkage which is not creating asset hierarchy."""
    return class_linkage[class_linkage.linking_type == "hierarchy"]


def _remove_higher_occurring_sym_pair(class_linkage: pd.DataFrame, sym_pairs: set[tuple[str, str]]) -> pd.DataFrame:
    """Remove symmetric pair which is higher in occurrence."""
    rows_to_remove = set()
    for source, target in sym_pairs:
        first_sym_property_occurrence = class_linkage[
            (class_linkage.source_class == source) & (class_linkage.target_class == target)
        ].max_occurrence.values[0]
        second_sym_property_occurrence = class_linkage[
            (class_linkage.source_class == target) & (class_linkage.target_class == source)
        ].max_occurrence.values[0]

        if first_sym_property_occurrence is None:
            # this means that source occurrence is unbounded
            index = class_linkage[
                (class_linkage.source_class == source) & (class_linkage.target_class == target)
            ].index.values[0]
        elif (
            second_sym_property_occurrence is None
            or first_sym_property_occurrence <= second_sym_property_occurrence
            and second_sym_property_occurrence > first_sym_property_occurrence
        ):
            # this means that target occurrence is unbounded
            index = class_linkage[
                (class_linkage.source_class == target) & (class_linkage.target_class == source)
            ].index.values[0]
        else:
            index = class_linkage[
                (class_linkage.source_class == source) & (class_linkage.target_class == target)
            ].index.values[0]
        rows_to_remove.add(index)

    return class_linkage.drop(list(rows_to_remove))


def _remove_non_requested_sym_pairs(class_linkage: pd.DataFrame, class_count: dict) -> pd.DataFrame:
    """Remove symmetric pairs which classes are not found in class count."""
    rows_to_remove = set(class_linkage[~(class_linkage["source_class"].isin(set(class_count.keys())))].index.values)
    rows_to_remove |= set(class_linkage[~(class_linkage["target_class"].isin(set(class_count.keys())))].index.values)

    return class_linkage.drop(list(rows_to_remove))


def _generate_mock_data_property_triples(
    instance_ids: list[URIRef], property_: str, namespace: Namespace, value_type: str = "string"
) -> list[tuple[URIRef, URIRef, Literal]]:
    """Generates triples for data properties."""

    python_type = XSD_VALUE_TYPE_MAPPINGS[value_type].python
    triples = []
    for id_ in instance_ids:
        if python_type == int:
            triples.append((id_, URIRef(namespace[property_]), Literal(random.randint(1, 1983))))
        elif python_type == float:
            triples.append((id_, URIRef(namespace[property_]), Literal(numpy.float32(random.uniform(1, 1983)))))
        # generate string
        else:
            triples.append((id_, URIRef(namespace[property_]), Literal(remove_namespace(id_).replace("-", " "))))
    return triples


def _generate_mock_object_property_triples(
    class_: str,
    property_definition: pd.Series,
    class_definitions: dict[str, pd.DataFrame],
    sym_pairs: set[tuple[str, str]],
    instance_ids: dict[str, list[URIRef]],
    namespace: Namespace,
    stop_on_exception: bool,
) -> list[tuple[URIRef, URIRef, URIRef]]:
    """Generates triples for object properties."""
    if property_definition.value_type not in instance_ids:
        msg = f"Class {property_definition.value_type} not found in class count! "
        if stop_on_exception:
            logging.error(msg)
            raise ValueError(msg)
        else:
            msg += (
                f"Skipping creating triples for property {property_definition.name} "
                f"of class {class_} which expects values of this type!"
            )
            logging.warning(msg)
            warnings.warn(msg, stacklevel=2)
            return []

    # Handling symmetric property
    symmetric_property = (
        class_definitions[property_definition.value_type][
            class_definitions[property_definition.value_type].value_type == class_
        ].index.values[0]
        if tuple((class_, property_definition.value_type)) in sym_pairs
        else None
    )

    triples = []

    for i, source in enumerate(instance_ids[class_]):
        target = instance_ids[property_definition.value_type][i % len(instance_ids[property_definition.value_type])]
        triples += [(URIRef(source), URIRef(namespace[str(property_definition.name)]), URIRef(target))]

        if symmetric_property:
            triples += [(URIRef(target), URIRef(namespace[symmetric_property]), URIRef(source))]

    # remove symmetric property from class definition of downstream class
    # to avoid asymmetric linking in mock graph
    if symmetric_property:
        class_definitions[property_definition.value_type].drop(symmetric_property, inplace=True)

    return triples


def _generate_triples_per_class(
    class_: str,
    class_definitions: dict[str, pd.DataFrame],
    sym_pairs: set[tuple[str, str]],
    instance_ids: dict[str, list[URIRef]],
    namespace: Namespace,
    stop_on_exception: bool,
) -> list[Triple]:
    """Generate triples for a given class."""
    triples: list[Triple] = []
    for _, property_definition in class_definitions[class_].iterrows():
        if property_definition.property_type == "DatatypeProperty":
            triples += _generate_mock_data_property_triples(
                instance_ids[class_], str(property_definition.name), namespace, property_definition.value_type
            )

        elif property_definition.property_type == "ObjectProperty":
            triples += _generate_mock_object_property_triples(
                class_, property_definition, class_definitions, sym_pairs, instance_ids, namespace, stop_on_exception
            )

        else:
            logging.error(f"Property type {property_definition.property_type} not supported!")
            raise ValueError(f"Property type {property_definition.property_type} not supported!")

    return triples


def _rules_to_dict(transformation_rules: Rules) -> dict[str, pd.DataFrame]:
    """Represent data model as a dictionary of data frames, where each data frame
    represents properties defined for a given class.

    Args:
        transformation_rules: Transformation rules defining the data model

    Returns:
        Simplified representation of the data model
    """

    data_model: dict[str, pd.DataFrame] = {}

    defined_classes = get_classes_with_properties(transformation_rules)

    for class_ in defined_classes:
        properties = {}
        for property_ in defined_classes[class_]:
            if property_.property_id not in properties:
                properties[property_.property_id] = {
                    "property_type": property_.property_type,
                    "value_type": property_.expected_value_type.suffix,
                    "min_count": property_.min_count,
                    "max_count": property_.max_count,
                }

        data_model[class_] = pd.DataFrame(properties).T
    return data_model
