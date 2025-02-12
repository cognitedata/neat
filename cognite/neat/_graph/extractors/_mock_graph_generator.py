"""This module is used to generate mock graph data for purposes of testing of NEAT.
It is a bit ugly and needs some proper refactoring, but it is not a priority at the moment.
"""

import random
import warnings
from collections import OrderedDict
from typing import cast

import numpy
import pandas as pd
from rdflib import RDF, Literal, Namespace, URIRef

from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.analysis import RulesAnalysis
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationProperty
from cognite.neat._rules.transformers import SubsetInformationRules
from cognite.neat._shared import Triple
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._base import BaseExtractor


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
        self,
        rules: InformationRules | DMSRules,
        class_count: dict[str | ClassEntity, int] | None = None,
        stop_on_exception: bool = False,
        allow_isolated_classes: bool = True,
    ):
        if isinstance(rules, DMSRules):
            # fixes potential issues with circular dependencies
            from cognite.neat._rules.transformers import DMSToInformation

            self.rules = DMSToInformation().transform(rules)
        elif isinstance(rules, InformationRules):
            self.rules = rules
        else:
            raise ValueError("Rules must be of type InformationRules or DMSRules!")

        if not class_count:
            self.class_count = {
                class_: 1 for class_ in RulesAnalysis(self.rules).defined_classes(include_ancestors=True)
            }
        elif all(isinstance(key, str) for key in class_count.keys()):
            self.class_count = {
                ClassEntity.load(f"{self.rules.metadata.prefix}:{key}"): value for key, value in class_count.items()
            }
        elif all(isinstance(key, ClassEntity) for key in class_count.keys()):
            self.class_count = cast(dict[ClassEntity, int], class_count)
        else:
            raise ValueError("Class count keys must be of type str! or ClassEntity! or empty dict!")

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
    rules: InformationRules,
    class_count: dict[ClassEntity, int],
    stop_on_exception: bool = False,
    allow_isolated_classes: bool = True,
) -> list[Triple]:
    """Generate mock triples based on data model defined in rules and desired number
    of class instances

    Args:
        rules : Rules defining the data model
        class_count: Target class count for each class in the ontology
        stop_on_exception: To stop if exception is encountered or not, default is False
        allow_isolated_classes: To allow generation of instances for classes that are not
                                 connected to any other class, default is True

    Returns:
        List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
    """

    namespace = rules.metadata.namespace
    analysis = RulesAnalysis(rules)
    defined_classes = analysis.defined_classes(include_ancestors=True)

    if non_existing_classes := set(class_count.keys()) - defined_classes:
        msg = f"Class count contains classes {non_existing_classes} for which properties are not defined in Data Model!"
        if stop_on_exception:
            raise ValueError(msg)
        else:
            msg += " These classes will be ignored."
            warnings.warn(msg, stacklevel=2)
            for class_ in non_existing_classes:
                class_count.pop(class_)

    # Subset data model to only classes that are defined in class count
    rules = (
        SubsetInformationRules(classes=set(class_count.keys())).transform(rules)
        if defined_classes != set(class_count.keys())
        else rules
    )

    class_linkage = analysis.class_linkage().to_pandas()

    # Remove one of symmetric pairs from class linkage to maintain proper linking
    # among instances of symmetrically linked classes
    if sym_pairs := analysis.symmetrically_connected_classes():
        class_linkage = _remove_higher_occurring_sym_pair(class_linkage, sym_pairs)

    # Remove any of symmetric pairs containing classes that are not present class count
    class_linkage = _remove_non_requested_sym_pairs(class_linkage, class_count)

    # Generate generation order for classes instances
    generation_order = _prettify_generation_order(_get_generation_order(class_linkage))

    # Generated simple view of data model
    class_property_pairs = analysis.properties_by_class(include_ancestors=True)

    # pregenerate instance ids for each remaining class
    instance_ids = {
        key: [URIRef(namespace[f"{key.suffix}-{i + 1}"]) for i in range(value)] for key, value in class_count.items()
    }

    # create triple for each class instance defining its type
    triples: list[Triple] = []
    for class_ in class_count:
        triples += [
            (class_instance_id, RDF.type, URIRef(namespace[str(class_.suffix)]))
            for class_instance_id in instance_ids[class_]
        ]

    # generate triples for connected classes
    for class_ in generation_order:
        triples += _generate_triples_per_class(
            class_,
            class_property_pairs,
            sym_pairs,
            instance_ids,
            namespace,
            stop_on_exception,
        )

    # generate triples for isolated classes
    if allow_isolated_classes:
        for class_ in set(class_count.keys()) - set(generation_order):
            triples += _generate_triples_per_class(
                class_,
                class_property_pairs,
                sym_pairs,
                instance_ids,
                namespace,
                stop_on_exception,
            )

    return triples


def _get_generation_order(
    class_linkage: pd.DataFrame,
    parent_col: str = "source_class",
    child_col: str = "target_class",
) -> dict:
    parent_child_list: list[list[str]] = class_linkage[[parent_col, child_col]].values.tolist()  # type: ignore[assignment]
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


def _remove_higher_occurring_sym_pair(
    class_linkage: pd.DataFrame, sym_pairs: set[tuple[ClassEntity, ClassEntity]]
) -> pd.DataFrame:
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
        elif second_sym_property_occurrence is None or (
            first_sym_property_occurrence <= second_sym_property_occurrence
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
    instance_ids: list[URIRef],
    property_: str,
    namespace: Namespace,
    value_type: DataType,
) -> list[tuple[URIRef, URIRef, Literal]]:
    """Generates triples for data properties."""

    python_type = value_type.python
    triples = []
    for id_ in instance_ids:
        if python_type is int:
            triples.append((id_, URIRef(namespace[property_]), Literal(random.randint(1, 1983))))
        elif python_type is float:
            triples.append(
                (
                    id_,
                    URIRef(namespace[property_]),
                    Literal(numpy.float32(random.uniform(1, 1983))),
                )
            )
        # generate string
        else:
            triples.append(
                (
                    id_,
                    URIRef(namespace[property_]),
                    Literal(f"{property_}-{remove_namespace_from_uri(id_).split('-')[-1]}"),
                )
            )
    return triples


def _generate_mock_object_property_triples(
    class_: ClassEntity,
    property_definition: InformationProperty,
    class_property_pairs: dict[ClassEntity, list[InformationProperty]],
    sym_pairs: set[tuple[ClassEntity, ClassEntity]],
    instance_ids: dict[ClassEntity, list[URIRef]],
    namespace: Namespace,
    stop_on_exception: bool,
) -> list[tuple[URIRef, URIRef, URIRef]]:
    """Generates triples for object properties."""
    if property_definition.value_type not in instance_ids:
        msg = f"Class {property_definition.value_type} not found in class count! "
        if stop_on_exception:
            raise ValueError(msg)
        else:
            msg += (
                f"Skipping creating triples for property {property_definition.name} "
                f"of class {class_.suffix} which expects values of this type!"
            )
            warnings.warn(msg, stacklevel=2)
            return []

    # Handling symmetric property

    if tuple((class_, property_definition.value_type)) in sym_pairs:
        symmetric_class_properties = class_property_pairs[cast(ClassEntity, property_definition.value_type)]
        candidates = list(
            filter(
                lambda instance: instance.value_type == class_,
                symmetric_class_properties,
            )
        )
        symmetric_property = candidates[0]
        if len(candidates) > 1:
            warnings.warn(
                f"Multiple symmetric properties found for class {property_definition.value_type}! "
                f"Only one will be used for creating symmetric triples.",
                stacklevel=2,
            )
    else:
        symmetric_property = None

    triples = []

    for i, source in enumerate(instance_ids[class_]):
        target = instance_ids[cast(ClassEntity, property_definition.value_type)][
            i % len(instance_ids[cast(ClassEntity, property_definition.value_type)])
        ]
        triples += [
            (
                URIRef(source),
                URIRef(namespace[property_definition.property_]),
                URIRef(target),
            )
        ]

        if symmetric_property:
            triples += [
                (
                    URIRef(target),
                    URIRef(namespace[symmetric_property.property_]),
                    URIRef(source),
                )
            ]

    if symmetric_property:
        class_property_pairs[cast(ClassEntity, property_definition.value_type)].remove(symmetric_property)

    return triples


def _generate_triples_per_class(
    class_: ClassEntity,
    class_properties_pairs: dict[ClassEntity, list[InformationProperty]],
    sym_pairs: set[tuple[ClassEntity, ClassEntity]],
    instance_ids: dict[ClassEntity, list[URIRef]],
    namespace: Namespace,
    stop_on_exception: bool,
) -> list[Triple]:
    """Generate triples for a given class."""
    triples: list[Triple] = []

    for property_ in class_properties_pairs[class_]:
        if property_.type_ == EntityTypes.data_property:
            triples += _generate_mock_data_property_triples(
                instance_ids[class_],
                property_.property_,
                namespace,
                cast(DataType, property_.value_type),
            )

        elif property_.type_ == EntityTypes.object_property:
            triples += _generate_mock_object_property_triples(
                class_,
                property_,
                class_properties_pairs,
                sym_pairs,
                instance_ids,
                namespace,
                stop_on_exception,
            )

        else:
            raise ValueError(f"Property type {property_.value_type} not supported!")

    return triples
