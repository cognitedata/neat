"""This module is used to generate mock graph data for purposes of testing of NEAT.
"""
import logging
import warnings

import pandas as pd
from prometheus_client import Gauge
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat.core.rules.models import TransformationRules
from cognite.neat.core.utils.utils import get_generation_order, prettify_generation_order, remove_namespace

neat_total_processed_mock_triples = Gauge(
    "neat_total_processed_mock_triples", "Number of processed mock triples", ["state"]
)
neat_mock_triples_processing_timing = Gauge(
    "neat_mock_triples_processing_timing", "Generation of mock knowledge graph timing metrics", ["aggregation"]
)


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

    return class_linkage.drop(rows_to_remove)


def _remove_non_requested_sym_pairs(class_linkage: pd.DataFrame, class_count: dict) -> pd.DataFrame:
    """Remove symmetric pairs which classes are not found in class count."""
    rows_to_remove = set(class_linkage[~(class_linkage["source_class"].isin(set(class_count.keys())))].index.values)
    rows_to_remove |= set(class_linkage[~(class_linkage["target_class"].isin(set(class_count.keys())))].index.values)

    return class_linkage.drop(rows_to_remove)


def _generate_mock_data_property_triples(
    instance_ids: list[URIRef], property_: str, namespace: Namespace
) -> list[tuple[URIRef, URIRef, Literal]]:
    """Generates triples for data properties."""
    # TODO: we should handle datatype, currently we are assuming everything is string
    return [
        (
            id_,
            URIRef(namespace[property_]),
            Literal(remove_namespace(id_).replace("-", " ")),
        )
        for id_ in instance_ids
    ]


def _generate_mock_object_property_triples(
    class_: str,
    property_definition: pd.Series,
    class_definitions: dict[str, pd.DataFrame],
    sym_pairs: set[tuple[str, str]],
    instance_ids: list[URIRef],
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
            msg += f"Skipping creating triples for property {property_definition.name} of class {class_} which expects values of this type!"
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
        triples += [
            (
                URIRef(source),
                URIRef(namespace[property_definition.name]),
                URIRef(target),
            )
        ]

        if symmetric_property:
            triples += [
                (
                    URIRef(target),
                    URIRef(namespace[symmetric_property]),
                    URIRef(source),
                )
            ]

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
) -> list[tuple]:
    """Generate triples for a given class."""
    triples = []
    for _, property_definition in class_definitions[class_].iterrows():
        if property_definition.property_type == "DatatypeProperty":
            triples += _generate_mock_data_property_triples(instance_ids[class_], property_definition.name, namespace)

        elif property_definition.property_type == "ObjectProperty":
            triples += _generate_mock_object_property_triples(
                class_,
                property_definition,
                class_definitions,
                sym_pairs,
                instance_ids,
                namespace,
                stop_on_exception,
            )

        else:
            logging.error(f"Property type {property_definition.property_type} not supported!")
            raise ValueError(f"Property type {property_definition.property_type} not supported!")

    return triples


def generate_triples(
    transformation_rules: TransformationRules,
    class_count: dict,
    stop_on_exception: bool = False,
    allow_isolated_classes: bool = True,
) -> list[tuple]:
    """Generate mock triples for purposes of testing of NEAT based on input transformation rules and desired class count.

    Parameters
    ----------
    data_model : DataModelingDefinition
        Data model containing ontology and object shape constraints for each class
    class_count : dict
        Target class count for each class in the ontology
    stop_on_exception: bool
        To stop if exception is encountered or not, default is False
    allow_isolated_classes: bool
        To allow generation of instances for classes that are not connected to any other class, default is True
    """

    # Figure out which classes are defined in the data model and which are not

    defined_classes = transformation_rules.get_defined_classes()

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
        transformation_rules.reduce_data_model(set(class_count.keys()), skip_validation=True)
        if transformation_rules.get_defined_classes() != set(class_count.keys())
        else transformation_rules
    )

    class_linkage = transformation_rules.get_class_linkage()

    # Remove one of symmetric pairs from class linkage to maintain proper linking
    # among instances of symmetrically linked classes
    if sym_pairs := transformation_rules.get_symmetric_pairs():
        class_linkage = _remove_higher_occurring_sym_pair(class_linkage, sym_pairs)

    # Remove any of symmetric pairs containing classes that are not present class count
    class_linkage = _remove_non_requested_sym_pairs(class_linkage, class_count)

    # Generate generation order for classes instances
    generation_order = prettify_generation_order(get_generation_order(class_linkage))

    # Generated simple view of data model
    class_definitions = transformation_rules.to_dataframe()

    # pregenerate instance ids for each remaining class
    instance_ids = {
        key: [URIRef(transformation_rules.metadata.namespace[f"{key}-{i}"]) for i in range(value)]
        for key, value in class_count.items()
    }

    # create triple for each class instance defining its type
    triples = []
    for class_ in class_count:
        triples += [
            (
                class_instance_id,
                RDF.type,
                URIRef(transformation_rules.metadata.namespace[class_]),
            )
            for class_instance_id in instance_ids[class_]
        ]

    # generate triples for connected classes
    for class_ in generation_order:
        triples += _generate_triples_per_class(
            class_,
            class_definitions,
            sym_pairs,
            instance_ids,
            transformation_rules.metadata.namespace,
            stop_on_exception,
        )

    # generate triples for isolated classes
    if allow_isolated_classes:
        for class_ in set(class_count.keys()) - set(generation_order):
            triples += _generate_triples_per_class(
                class_,
                class_definitions,
                sym_pairs,
                instance_ids,
                transformation_rules.metadata.namespace,
                stop_on_exception,
            )

    return triples
