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

from cognite.neat.v0.core._data_model._constants import EntityTypes
from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.v0.core._data_model.models.conceptual import ConceptualProperty
from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities import ConceptEntity
from cognite.neat.v0.core._data_model.transformers import SubsetConceptualDataModel
from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._utils.rdf_ import remove_namespace_from_uri

from ._base import BaseExtractor


class MockGraphGenerator(BaseExtractor):
    """
    Class used to generate mock graph data for purposes of testing of NEAT.

    Args:
        data_model: Data model defining the concepts with their properties.
        concept_count: Target concept count for each concept/class in the data model
        stop_on_exception: To stop if exception is encountered or not, default is False
        allow_isolated_classes: To allow generation of instances for classes that are not
                                 connected to any other class, default is True
    """

    def __init__(
        self,
        data_model: ConceptualDataModel | PhysicalDataModel,
        concept_count: dict[str | ConceptEntity, int] | None = None,
        stop_on_exception: bool = False,
        allow_isolated_classes: bool = True,
    ):
        if isinstance(data_model, PhysicalDataModel):
            # fixes potential issues with circular dependencies
            from cognite.neat.v0.core._data_model.transformers import PhysicalToConceptual

            self.data_model = PhysicalToConceptual().transform(data_model)
        elif isinstance(data_model, ConceptualDataModel):
            self.data_model = data_model
        else:
            raise ValueError("Data model must be of type Conceptual or Physical!")

        if not concept_count:
            self.concept_count = {
                concept: 1 for concept in DataModelAnalysis(self.data_model).defined_concepts(include_ancestors=True)
            }
        elif all(isinstance(key, str) for key in concept_count.keys()):
            self.concept_count = {
                ConceptEntity.load(f"{self.data_model.metadata.prefix}:{key}"): value
                for key, value in concept_count.items()
            }
        elif all(isinstance(key, ConceptEntity) for key in concept_count.keys()):
            self.concept_count = cast(dict[ConceptEntity, int], concept_count)
        else:
            raise ValueError("Class count keys must be of type str! or ConceptEntity! or empty dict!")

        self.stop_on_exception = stop_on_exception
        self.allow_isolated_classes = allow_isolated_classes

    def extract(self) -> list[Triple]:
        """Generate mock triples based on data model and desired number
        of concept instances

        Returns:
            List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
        """
        return generate_triples(
            self.data_model,
            self.concept_count,
            stop_on_exception=self.stop_on_exception,
            allow_isolated_concepts=self.allow_isolated_classes,
        )


def generate_triples(
    data_model: ConceptualDataModel,
    concept_count: dict[ConceptEntity, int],
    stop_on_exception: bool = False,
    allow_isolated_concepts: bool = True,
) -> list[Triple]:
    """Generate mock triples based on the conceptual data model defined and desired number
    of class instances

    Args:
        data_model : Data model
        concept_count: Target concept count for each class in the data model
        stop_on_exception: To stop if exception is encountered or not, default is False
        allow_isolated_concepts: To allow generation of instances for classes that are not
                                 connected to any other class, default is True

    Returns:
        List of RDF triples, represented as tuples `(subject, predicate, object)`, that define data model instances
    """

    namespace = data_model.metadata.namespace
    analysis = DataModelAnalysis(data_model)
    defined_concepts = analysis.defined_concepts(include_ancestors=True)

    if non_existing_concepts := set(concept_count.keys()) - defined_concepts:
        msg = (
            f"Concept count contains concepts {non_existing_concepts} for which"
            " properties are not defined in Data Model!"
        )
        if stop_on_exception:
            raise ValueError(msg)
        else:
            msg += " These classes will be ignored."
            warnings.warn(msg, stacklevel=2)
            for concept in non_existing_concepts:
                concept_count.pop(concept)

    # Subset data model to only classes that are defined in class count
    data_model = (
        SubsetConceptualDataModel(concepts=set(concept_count.keys())).transform(data_model)
        if defined_concepts != set(concept_count.keys())
        else data_model
    )

    concept_linkage = analysis.concept_linkage().to_pandas()

    # Remove one of symmetric pairs from class linkage to maintain proper linking
    # among instances of symmetrically linked classes
    if sym_pairs := analysis.symmetrically_connected_concepts():
        concept_linkage = _remove_higher_occurring_sym_pair(concept_linkage, sym_pairs)

    # Remove any of symmetric pairs containing classes that are not present class count
    concept_linkage = _remove_non_requested_sym_pairs(concept_linkage, concept_count)

    # Generate generation order for classes instances
    generation_order = _prettify_generation_order(_get_generation_order(concept_linkage))

    # Generated simple view of data model
    properties_by_concepts = analysis.properties_by_concepts(include_ancestors=True)

    # pregenerate instance ids for each remaining class
    instance_ids = {
        key: [URIRef(namespace[f"{key.suffix}-{i + 1}"]) for i in range(value)] for key, value in concept_count.items()
    }

    # create triple for each class instance defining its type
    triples: list[Triple] = []
    for concept in concept_count:
        triples += [
            (concept_instance_id, RDF.type, URIRef(namespace[str(concept.suffix)]))
            for concept_instance_id in instance_ids[concept]
        ]

    # generate triples for connected classes
    for concept in generation_order:
        triples += _generate_triples_per_class(
            concept,
            properties_by_concepts,
            sym_pairs,
            instance_ids,
            namespace,
            stop_on_exception,
        )

    # generate triples for isolated classes
    if allow_isolated_concepts:
        for concept in set(concept_count.keys()) - set(generation_order):
            triples += _generate_triples_per_class(
                concept,
                properties_by_concepts,
                sym_pairs,
                instance_ids,
                namespace,
                stop_on_exception,
            )

    return triples


def _get_generation_order(
    concept_linkage: pd.DataFrame,
    parent_col: str = "source_class",
    child_col: str = "target_class",
) -> dict:
    parent_child_list: list[list[str]] = concept_linkage[[parent_col, child_col]].values.tolist()  # type: ignore[assignment]
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


def _prettify_generation_order(generation_order: dict, depth: dict | None = None, start: int = -1) -> dict:
    """Prettifies generation order dictionary for easier consumption."""
    depth = depth or {}
    for key, value in generation_order.items():
        depth[key] = start + 1
        if isinstance(value, dict):
            _prettify_generation_order(value, depth, start=start + 1)
    return OrderedDict(sorted(depth.items(), key=lambda item: item[1]))


def _remove_higher_occurring_sym_pair(
    concept_linkage: pd.DataFrame, sym_pairs: set[tuple[ConceptEntity, ConceptEntity]]
) -> pd.DataFrame:
    """Remove symmetric pair which is higher in occurrence."""
    rows_to_remove = set()
    for source, target in sym_pairs:
        first_sym_property_occurrence = concept_linkage[
            (concept_linkage.source_class == source) & (concept_linkage.target_class == target)
        ].max_occurrence.values[0]
        second_sym_property_occurrence = concept_linkage[
            (concept_linkage.source_class == target) & (concept_linkage.target_class == source)
        ].max_occurrence.values[0]

        if first_sym_property_occurrence is None:
            # this means that source occurrence is unbounded
            index = concept_linkage[
                (concept_linkage.source_class == source) & (concept_linkage.target_class == target)
            ].index.values[0]
        elif second_sym_property_occurrence is None or (
            first_sym_property_occurrence <= second_sym_property_occurrence
            and second_sym_property_occurrence > first_sym_property_occurrence
        ):
            # this means that target occurrence is unbounded
            index = concept_linkage[
                (concept_linkage.source_class == target) & (concept_linkage.target_class == source)
            ].index.values[0]
        else:
            index = concept_linkage[
                (concept_linkage.source_class == source) & (concept_linkage.target_class == target)
            ].index.values[0]
        rows_to_remove.add(index)

    return concept_linkage.drop(list(rows_to_remove))


def _remove_non_requested_sym_pairs(class_linkage: pd.DataFrame, concept_count: dict) -> pd.DataFrame:
    """Remove symmetric pairs which classes are not found in class count."""
    rows_to_remove = set(class_linkage[~(class_linkage["source_class"].isin(set(concept_count.keys())))].index.values)
    rows_to_remove |= set(class_linkage[~(class_linkage["target_class"].isin(set(concept_count.keys())))].index.values)

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
    concept: ConceptEntity,
    property_definition: ConceptualProperty,
    concept_property_pairs: dict[ConceptEntity, list[ConceptualProperty]],
    sym_pairs: set[tuple[ConceptEntity, ConceptEntity]],
    instance_ids: dict[ConceptEntity, list[URIRef]],
    namespace: Namespace,
    stop_on_exception: bool,
) -> list[tuple[URIRef, URIRef, URIRef]]:
    """Generates triples for object properties."""
    if property_definition.value_type not in instance_ids:
        msg = f"Concept {property_definition.value_type} not found in concept count! "
        if stop_on_exception:
            raise ValueError(msg)
        else:
            msg += (
                f"Skipping creating triples for property {property_definition.name} "
                f"of concept {concept.suffix} which expects values of this type!"
            )
            warnings.warn(msg, stacklevel=2)
            return []

    # Handling symmetric property

    if tuple((concept, property_definition.value_type)) in sym_pairs:
        symmetric_concept_properties = concept_property_pairs[cast(ConceptEntity, property_definition.value_type)]
        candidates = list(
            filter(
                lambda instance: instance.value_type == concept,
                symmetric_concept_properties,
            )
        )
        symmetric_property = candidates[0]
        if len(candidates) > 1:
            warnings.warn(
                f"Multiple symmetric properties found for concept {property_definition.value_type}! "
                f"Only one will be used for creating symmetric triples.",
                stacklevel=2,
            )
    else:
        symmetric_property = None

    triples = []

    for i, source in enumerate(instance_ids[concept]):
        target = instance_ids[cast(ConceptEntity, property_definition.value_type)][
            i % len(instance_ids[cast(ConceptEntity, property_definition.value_type)])
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
        concept_property_pairs[cast(ConceptEntity, property_definition.value_type)].remove(symmetric_property)

    return triples


def _generate_triples_per_class(
    concept: ConceptEntity,
    concept_properties_pairs: dict[ConceptEntity, list[ConceptualProperty]],
    sym_pairs: set[tuple[ConceptEntity, ConceptEntity]],
    instance_ids: dict[ConceptEntity, list[URIRef]],
    namespace: Namespace,
    stop_on_exception: bool,
) -> list[Triple]:
    """Generate triples for a given class."""
    triples: list[Triple] = []

    for property_ in concept_properties_pairs[concept]:
        if property_.type_ == EntityTypes.data_property:
            triples += _generate_mock_data_property_triples(
                instance_ids[concept],
                property_.property_,
                namespace,
                cast(DataType, property_.value_type),
            )

        elif property_.type_ == EntityTypes.object_property:
            triples += _generate_mock_object_property_triples(
                concept,
                property_,
                concept_properties_pairs,
                sym_pairs,
                instance_ids,
                namespace,
                stop_on_exception,
            )

        else:
            raise ValueError(f"Property type {property_.value_type} not supported!")

    return triples
