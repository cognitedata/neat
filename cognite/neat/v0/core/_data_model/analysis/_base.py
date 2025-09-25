import itertools
import warnings
from collections import defaultdict
from collections.abc import Hashable, ItemsView, Iterator, KeysView, MutableMapping, Set, ValuesView
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from typing import Any, Literal, TypeVar, overload

import networkx as nx
import pandas as pd
from cognite.client import data_modeling as dm
from rdflib import URIRef

from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.v0.core._data_model.models.conceptual import (
    Concept,
    ConceptualProperty,
)
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptEntity,
    MultiValueTypeInfo,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import (
    UnknownEntity,
)
from cognite.neat.v0.core._data_model.models.physical import PhysicalProperty
from cognite.neat.v0.core._data_model.models.physical._verified import PhysicalView
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._issues.warnings import NeatValueWarning

T_Hashable = TypeVar("T_Hashable", bound=Hashable)


@dataclass(frozen=True)
class Linkage:
    source_concept: ConceptEntity
    connecting_property: str
    target_concept: ConceptEntity
    max_occurrence: int | float | None


class LinkageSet(set, Set[Linkage]):
    @property
    def source_concept(self) -> set[ConceptEntity]:
        return {link.source_concept for link in self}

    @property
    def target_concept(self) -> set[ConceptEntity]:
        return {link.target_concept for link in self}

    def get_target_concepts_by_source(self) -> dict[ConceptEntity, set[ConceptEntity]]:
        target_concepts_by_source: dict[ConceptEntity, set[ConceptEntity]] = defaultdict(set)
        for link in self:
            target_concepts_by_source[link.source_concept].add(link.target_concept)
        return target_concepts_by_source

    def to_pandas(self) -> pd.DataFrame:
        # Todo: Remove this method
        return pd.DataFrame(
            [
                {
                    "source_concept": link.source_concept,
                    "connecting_property": link.connecting_property,
                    "target_concept": link.target_concept,
                    "max_occurrence": link.max_occurrence,
                }
                for link in self
            ]
        )


@dataclass
class ViewQuery:
    view_id: dm.ViewId
    rdf_type: URIRef
    property_renaming_config: dict[URIRef, str] = field(default_factory=dict)


class ViewQueryDict(dict, MutableMapping[dm.ViewId, ViewQuery]):
    # The below methods are included to make better type hints in the IDE
    def __getitem__(self, k: dm.ViewId) -> ViewQuery:
        return super().__getitem__(k)

    def __setitem__(self, k: dm.ViewId, v: ViewQuery) -> None:
        super().__setitem__(k, v)

    def __delitem__(self, k: dm.ViewId) -> None:
        super().__delitem__(k)

    def __iter__(self) -> Iterator[dm.ViewId]:
        return super().__iter__()

    def keys(self) -> KeysView[dm.ViewId]:  # type: ignore[override]
        return super().keys()

    def values(self) -> ValuesView[ViewQuery]:  # type: ignore[override]
        return super().values()

    def items(self) -> ItemsView[dm.ViewId, ViewQuery]:  # type: ignore[override]
        return super().items()

    def get(self, __key: dm.ViewId, __default: Any = ...) -> ViewQuery:
        return super().get(__key, __default)

    def pop(self, __key: dm.ViewId, __default: Any = ...) -> ViewQuery:
        return super().pop(__key, __default)

    def popitem(self) -> tuple[dm.ViewId, ViewQuery]:
        return super().popitem()


class DataModelAnalysis:
    def __init__(
        self,
        conceptual: ConceptualDataModel | None = None,
        physical: PhysicalDataModel | None = None,
    ) -> None:
        self._conceptual = conceptual
        self._physical = physical

    @property
    def conceptual(self) -> ConceptualDataModel:
        if self._conceptual is None:
            raise NeatValueError("Conceptual Data Model is required for this analysis")
        return self._conceptual

    @property
    def physical(self) -> PhysicalDataModel:
        if self._physical is None:
            raise NeatValueError("Physical Data Model is required for this analysis")
        return self._physical

    def parents_by_concept(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ConceptEntity, set[ConceptEntity]]:
        """Get a dictionary of concepts and their parents.

        Args:
            include_ancestors (bool, optional): Include ancestors of the parents. Defaults to False.
            include_different_space (bool, optional): Include parents from different spaces. Defaults to False.

        Returns:
            dict[ConceptEntity, set[ConceptEntity]]: Values parents with concept as key.
        """
        parents_by_concept: dict[ConceptEntity, set[ConceptEntity]] = {}
        for concept in self.conceptual.concepts:
            parents_by_concept[concept.concept] = set()
            for parent in concept.implements or []:
                if include_different_space or parent.prefix == concept.concept.prefix:
                    parents_by_concept[concept.concept].add(parent)
                else:
                    warnings.warn(
                        NeatValueWarning(
                            f"Parent concept {parent} of concept {concept} is not in the same namespace, skipping!"
                        ),
                        stacklevel=2,
                    )
        if include_ancestors:
            self._include_ancestors(parents_by_concept)

        return parents_by_concept

    @staticmethod
    def _include_ancestors(
        parents_by_concept: dict[T_Hashable, set[T_Hashable]],
    ) -> None:
        # Topological sort to ensure that concepts include all ancestors
        for concept_entity in list(TopologicalSorter(parents_by_concept).static_order()):
            if concept_entity not in parents_by_concept:
                continue
            parents_by_concept[concept_entity] |= {
                grand_parent
                for parent in parents_by_concept[concept_entity]
                for grand_parent in parents_by_concept.get(parent, set())
            }

    def properties_by_concepts(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ConceptEntity, list[ConceptualProperty]]:
        """Get a dictionary of concepts and their properties.

        Args:
            include_ancestors: Whether to include properties from parent concepts.
            include_different_space: Whether to include properties from parent concepts in different spaces.

        Returns:
            dict[ConceptEntity, list[ConceptualProperty]]: Values properties with concept as key.

        """
        properties_by_concepts: dict[ConceptEntity, list[ConceptualProperty]] = defaultdict(list)
        for prop in self.conceptual.properties:
            properties_by_concepts[prop.concept].append(prop)

        if include_ancestors:
            parents_by_concepts = self.parents_by_concept(
                include_ancestors=include_ancestors,
                include_different_space=include_different_space,
            )
            for concept, parents in parents_by_concepts.items():
                concept_properties = {prop.property_ for prop in properties_by_concepts[concept]}
                for parent in parents:
                    for parent_prop in properties_by_concepts[parent]:
                        if parent_prop.property_ not in concept_properties:
                            child_prop = parent_prop.model_copy(update={"concept": concept})
                            properties_by_concepts[concept].append(child_prop)
                            concept_properties.add(child_prop.property_)

        return properties_by_concepts

    def implements_by_view(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ViewEntity, set[ViewEntity]]:
        """Get a dictionary of views and their implemented views."""
        # This is a duplicate fo the parent_by_concept method, but for views
        # The choice to duplicate the code is to avoid generics which will make the code less readable
        implements_by_view: dict[ViewEntity, set[ViewEntity]] = {}
        for view in self.physical.views:
            implements_by_view[view.view] = set()
            for implements in view.implements or []:
                if include_different_space or implements.space == view.view.space:
                    implements_by_view[view.view].add(implements)
                else:
                    warnings.warn(
                        NeatValueWarning(
                            f"Implemented view {implements} of view {view} is not in the same namespace, skipping!"
                        ),
                        stacklevel=2,
                    )
        if include_ancestors:
            self._include_ancestors(implements_by_view)
        return implements_by_view

    def properties_by_view(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ViewEntity, list[PhysicalProperty]]:
        """Get a dictionary of views and their properties."""
        # This is a duplicate fo the properties_by_concept method, but for views
        # The choice to duplicate the code is to avoid generics which will make the code less readable.
        properties_by_views: dict[ViewEntity, list[PhysicalProperty]] = defaultdict(list)
        for prop in self.physical.properties:
            properties_by_views[prop.view].append(prop)

        if include_ancestors:
            implements_by_view = self.implements_by_view(
                include_ancestors=include_ancestors, include_different_space=include_different_space
            )
            for view, parents in implements_by_view.items():
                view_properties = {prop.view_property for prop in properties_by_views[view]}
                for parent in parents:
                    for parent_prop in properties_by_views[parent]:
                        if parent_prop.view_property not in view_properties:
                            child_prop = parent_prop.model_copy(update={"view": view})
                            properties_by_views[view].append(child_prop)
                            view_properties.add(child_prop.view_property)

        return properties_by_views

    @property
    def conceptual_uri_by_view(self) -> dict[ViewEntity, URIRef]:
        """Get the logical URI by view."""
        return {view.view: view.conceptual for view in self.physical.views if view.conceptual}

    def conceptual_uri_by_property_by_view(
        self,
        include_ancestors: bool = False,
        include_different_space: bool = False,
    ) -> dict[ViewEntity, dict[str, URIRef]]:
        """Get the logical URI by property by view."""
        properties_by_view = self.properties_by_view(include_ancestors, include_different_space)

        return {
            view: {prop.view_property: prop.conceptual for prop in properties if prop.conceptual}
            for view, properties in properties_by_view.items()
        }

    @property
    def _concept_by_neat_id(self) -> dict[URIRef, Concept]:
        """Get a dictionary of concept neat IDs to
        concept entities."""

        return {cls.neatId: cls for cls in self.conceptual.concepts if cls.neatId}

    def concept_by_suffix(self) -> dict[str, Concept]:
        """Get a dictionary of concept suffixes to concept entities."""
        # TODO: Remove this method
        concept_dict: dict[str, Concept] = {}
        for definition in self.conceptual.concepts:
            entity = definition.concept
            if entity.suffix in concept_dict:
                warnings.warn(
                    NeatValueWarning(
                        f"Concept {entity} has been defined more than once! Only the first definition "
                        "will be considered, skipping the rest.."
                    ),
                    stacklevel=2,
                )
                continue
            concept_dict[entity.suffix] = definition
        return concept_dict

    @property
    def concept_by_concept_entity(self) -> dict[ConceptEntity, Concept]:
        """Get a dictionary of concept entities to concept entities."""
        data_model = self.conceptual
        return {cls.concept: cls for cls in data_model.concepts}

    @property
    def view_by_view_entity(self) -> dict[ViewEntity, PhysicalView]:
        """Get a dictionary of views to view entities."""
        data_model = self.physical
        return {view.view: view for view in data_model.views}

    def property_by_id(self) -> dict[str, list[ConceptualProperty]]:
        """Get a dictionary of property IDs to property entities."""
        property_dict: dict[str, list[ConceptualProperty]] = defaultdict(list)
        for prop in self.conceptual.properties:
            property_dict[prop.property_].append(prop)
        return property_dict

    def properties_by_id_by_concept(
        self,
        has_instance_source: bool = False,
        include_ancestors: bool = False,
    ) -> dict[ConceptEntity, dict[str, ConceptualProperty]]:
        """Get a dictionary of concept entities to dictionaries of property IDs to property entities."""
        concept_property_pairs: dict[ConceptEntity, dict[str, ConceptualProperty]] = {}
        for concept, properties in self.properties_by_concepts(include_ancestors).items():
            processed_properties: dict[str, ConceptualProperty] = {}
            for prop in properties:
                if prop.property_ in processed_properties:
                    warnings.warn(
                        NeatValueWarning(
                            f"Property {processed_properties} for {concept} has been defined more than once!"
                            " Only the first definition will be considered, skipping the rest.."
                        ),
                        stacklevel=2,
                    )
                    continue
                if has_instance_source and prop.instance_source is None:
                    continue
                processed_properties[prop.property_] = prop
            concept_property_pairs[concept] = processed_properties

        return concept_property_pairs

    def defined_views(self, include_ancestors: bool = False) -> set[ViewEntity]:
        properties_by_view = self.properties_by_view(include_ancestors)
        return {prop.view for prop in itertools.chain.from_iterable(properties_by_view.values())}

    def concepts(self) -> set[ConceptEntity]:
        """Returns all concepts defined Concepts in the data model."""
        return {concept.concept for concept in self.conceptual.concepts}

    def defined_concepts(
        self,
        include_ancestors: bool = False,
    ) -> set[ConceptEntity]:
        """Returns concepts that have properties defined for them in the data model.

        Args:
            include_ancestors: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of concepts that have been defined in the data model
        """
        properties_by_concept = self.properties_by_concepts(include_ancestors)
        return {prop.concept for prop in itertools.chain.from_iterable(properties_by_concept.values())}

    def concept_linkage(
        self,
        include_ancestors: bool = False,
    ) -> LinkageSet:
        """Returns a set of concept linkages in the data model.

        Args:
            include_ancestors: Whether to consider inheritance or not. Defaults False

        Returns:

        """
        concept_linkage = LinkageSet()

        properties_by_concept = self.properties_by_concepts(include_ancestors)

        prop: ConceptualProperty
        for prop in itertools.chain.from_iterable(properties_by_concept.values()):
            if not isinstance(prop.value_type, ConceptEntity):
                continue
            concept_linkage.add(
                Linkage(
                    source_concept=prop.concept,
                    connecting_property=prop.property_,
                    target_concept=prop.value_type,
                    max_occurrence=prop.max_count,
                )
            )

        return concept_linkage

    def symmetrically_connected_concepts(
        self,
        include_ancestors: bool = False,
    ) -> set[tuple[ConceptEntity, ConceptEntity]]:
        """Returns a set of pairs of symmetrically linked concepts.

        Args:
            include_ancestors: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of pairs of symmetrically linked concepts

        !!! note "Symmetrically Connected Concepts"
            Symmetrically connected concepts are concepts that are connected to each other
            in both directions. For example, if concept A is connected to concept B, and concept B
            is connected to concept A, then concepts A and B are symmetrically connected.
        """
        sym_pairs: set[tuple[ConceptEntity, ConceptEntity]] = set()
        concept_linkage = self.concept_linkage(include_ancestors)
        if not concept_linkage:
            return sym_pairs

        targets_by_source = concept_linkage.get_target_concepts_by_source()
        for link in concept_linkage:
            source = link.source_concept
            target = link.target_concept

            if source in targets_by_source[source] and (source, target) not in sym_pairs:
                sym_pairs.add((source, target))
        return sym_pairs

    @overload
    def _properties_by_neat_id(self, format: Literal["info"] = "info") -> dict[URIRef, ConceptualProperty]: ...

    @overload
    def _properties_by_neat_id(self, format: Literal["dms"] = "dms") -> dict[URIRef, PhysicalProperty]: ...

    def _properties_by_neat_id(
        self, format: Literal["info", "dms"] = "info"
    ) -> dict[URIRef, ConceptualProperty] | dict[URIRef, PhysicalProperty]:
        if format == "info":
            return {prop.neatId: prop for prop in self.conceptual.properties if prop.neatId}
        elif format == "dms":
            return {prop.neatId: prop for prop in self.physical.properties if prop.neatId}
        else:
            raise NeatValueError(f"Invalid format: {format}")

    @property
    def concepts_by_neat_id(self) -> dict[URIRef, Concept]:
        return {concept.neatId: concept for concept in self.conceptual.concepts if concept.neatId}

    @property
    def multi_value_properties(self) -> list[ConceptualProperty]:
        return [prop_ for prop_ in self.conceptual.properties if isinstance(prop_.value_type, MultiValueTypeInfo)]

    @property
    def view_query_by_id(
        self,
    ) -> "ViewQueryDict":
        # Trigger error if any of these are missing
        _ = self.conceptual
        _ = self.physical

        # caching results for faster access
        concepts_by_neat_id = self._concept_by_neat_id
        properties_by_concept = self.properties_by_concepts(include_ancestors=True)
        conceptual_uri_by_view = self.conceptual_uri_by_view
        conceptual_uri_by_property_by_view = self.conceptual_uri_by_property_by_view(include_ancestors=True)
        conceptual_properties_by_neat_id = self._properties_by_neat_id()

        query_configs = ViewQueryDict()
        for view in self.physical.views:
            # this entire block of sequential if statements checks:
            # 1. connection of physical and conceptual data model
            # 2. correct paring of conceptual and physical data model
            # 3. connection of conceptual data model to instances
            if (
                (neat_id := conceptual_uri_by_view.get(view.view))
                and (concept := concepts_by_neat_id.get(neat_id))
                and (uri := concept.instance_source)
            ):
                view_query = ViewQuery(
                    view_id=view.view.as_id(),
                    rdf_type=uri,
                    # start off with renaming of properties on the information level
                    # this is to encounter for special cases of e.g. space, startNode and endNode
                    property_renaming_config=(
                        {uri: prop_.property_ for prop_ in info_properties for uri in prop_.instance_source or []}
                        if (info_properties := properties_by_concept.get(concept.concept))
                        else {}
                    ),
                )

                if conceptual_uri_by_property := conceptual_uri_by_property_by_view.get(view.view):
                    for target_name, neat_id in conceptual_uri_by_property.items():
                        if (property_ := conceptual_properties_by_neat_id.get(neat_id)) and (
                            uris := property_.instance_source
                        ):
                            for uri in uris:
                                view_query.property_renaming_config[uri] = target_name

                query_configs[view.view.as_id()] = view_query

        return query_configs

    def _physical_di_graph(self, format: Literal["data-model", "implements"] = "data-model") -> nx.MultiDiGraph:
        """Generate a MultiDiGraph from the Physical Data Model."""
        di_graph = nx.MultiDiGraph()

        data_model = self.physical

        # Add nodes and edges from Views sheet
        for view in data_model.views:
            di_graph.add_node(view.view.suffix, label=view.view.suffix)

            if format == "implements" and view.implements:
                for implement in view.implements:
                    di_graph.add_node(implement.suffix, label=implement.suffix)
                    di_graph.add_edge(
                        view.view.suffix,
                        implement.suffix,
                        label="implements",
                        dashes=True,
                    )

        if format == "data-model":
            # Add nodes and edges from Properties sheet
            for prop_ in data_model.properties:
                if prop_.connection and isinstance(prop_.value_type, ViewEntity):
                    di_graph.add_node(prop_.view.suffix, label=prop_.view.suffix)
                    di_graph.add_node(prop_.value_type.suffix, label=prop_.value_type.suffix)
                    di_graph.add_edge(
                        prop_.view.suffix,
                        prop_.value_type.suffix,
                        label=prop_.name or prop_.view_property,
                    )

        return di_graph

    def _conceptual_di_graph(self, format: Literal["data-model", "implements"] = "data-model") -> nx.MultiDiGraph:
        """Generate MultiDiGraph representing conceptual data model."""

        data_model = self.conceptual
        di_graph = nx.MultiDiGraph()

        # Add nodes and edges from Views sheet
        for concept in data_model.concepts:
            # if possible use human readable label coming from the view name

            di_graph.add_node(
                concept.concept.suffix,
                label=concept.name or concept.concept.suffix,
            )

            if format == "implements" and concept.implements:
                for parent in concept.implements:
                    di_graph.add_node(parent.suffix, label=parent.suffix)
                    di_graph.add_edge(
                        concept.concept.suffix,
                        parent.suffix,
                        label="implements",
                        dashes=True,
                    )

        if format == "data-model":
            # Add nodes and edges from Properties sheet
            for prop_ in data_model.properties:
                if isinstance(prop_.value_type, ConceptEntity) and not isinstance(prop_.value_type, UnknownEntity):
                    di_graph.add_node(prop_.concept.suffix, label=prop_.concept.suffix)
                    di_graph.add_node(prop_.value_type.suffix, label=prop_.value_type.suffix)

                    di_graph.add_edge(
                        prop_.concept.suffix,
                        prop_.value_type.suffix,
                        label=prop_.name or prop_.property_,
                    )

        return di_graph
