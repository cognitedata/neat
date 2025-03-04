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

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models.dms import DMSProperty
from cognite.neat._rules.models.dms._rules import DMSView
from cognite.neat._rules.models.entities import ClassEntity, MultiValueTypeInfo, ViewEntity
from cognite.neat._rules.models.entities._single_value import (
    UnknownEntity,
)
from cognite.neat._rules.models.information import InformationClass, InformationProperty

T_Hashable = TypeVar("T_Hashable", bound=Hashable)


@dataclass(frozen=True)
class Linkage:
    source_class: ClassEntity
    connecting_property: str
    target_class: ClassEntity
    max_occurrence: int | float | None


class LinkageSet(set, Set[Linkage]):
    @property
    def source_class(self) -> set[ClassEntity]:
        return {link.source_class for link in self}

    @property
    def target_class(self) -> set[ClassEntity]:
        return {link.target_class for link in self}

    def get_target_classes_by_source(self) -> dict[ClassEntity, set[ClassEntity]]:
        target_classes_by_source: dict[ClassEntity, set[ClassEntity]] = defaultdict(set)
        for link in self:
            target_classes_by_source[link.source_class].add(link.target_class)
        return target_classes_by_source

    def to_pandas(self) -> pd.DataFrame:
        # Todo: Remove this method
        return pd.DataFrame(
            [
                {
                    "source_class": link.source_class,
                    "connecting_property": link.connecting_property,
                    "target_class": link.target_class,
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


class RulesAnalysis:
    def __init__(self, information: InformationRules | None = None, dms: DMSRules | None = None) -> None:
        self._information = information
        self._dms = dms

    @property
    def information(self) -> InformationRules:
        if self._information is None:
            raise NeatValueError("Information rules are required for this analysis")
        return self._information

    @property
    def dms(self) -> DMSRules:
        if self._dms is None:
            raise NeatValueError("DMS rules are required for this analysis")
        return self._dms

    def parents_by_class(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ClassEntity, set[ClassEntity]]:
        """Get a dictionary of classes and their parents.

        Args:
            include_ancestors (bool, optional): Include ancestors of the parents. Defaults to False.
            include_different_space (bool, optional): Include parents from different spaces. Defaults to False.

        Returns:
            dict[ClassEntity, set[ClassEntity]]: Values parents with class as key.
        """
        parents_by_class: dict[ClassEntity, set[ClassEntity]] = {}
        for class_ in self.information.classes:
            parents_by_class[class_.class_] = set()
            for parent in class_.implements or []:
                if include_different_space or parent.prefix == class_.class_.prefix:
                    parents_by_class[class_.class_].add(parent)
                else:
                    warnings.warn(
                        NeatValueWarning(
                            f"Parent class {parent} of class {class_} is not in the same namespace, skipping!"
                        ),
                        stacklevel=2,
                    )
        if include_ancestors:
            self._include_ancestors(parents_by_class)

        return parents_by_class

    @staticmethod
    def _include_ancestors(parents_by_class: dict[T_Hashable, set[T_Hashable]]) -> None:
        # Topological sort to ensure that classes include all ancestors
        for class_entity in list(TopologicalSorter(parents_by_class).static_order()):
            parents_by_class[class_entity] |= {
                grand_parent for parent in parents_by_class[class_entity] for grand_parent in parents_by_class[parent]
            }

    def properties_by_class(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ClassEntity, list[InformationProperty]]:
        """Get a dictionary of classes and their properties.

        Args:
            include_ancestors: Whether to include properties from parent classes.
            include_different_space: Whether to include properties from parent classes in different spaces.

        Returns:
            dict[ClassEntity, list[InformationProperty]]: Values properties with class as key.

        """
        properties_by_classes: dict[ClassEntity, list[InformationProperty]] = defaultdict(list)
        for prop in self.information.properties:
            properties_by_classes[prop.class_].append(prop)

        if include_ancestors:
            parents_by_classes = self.parents_by_class(
                include_ancestors=include_ancestors, include_different_space=include_different_space
            )
            for class_, parents in parents_by_classes.items():
                class_properties = {prop.property_ for prop in properties_by_classes[class_]}
                for parent in parents:
                    for parent_prop in properties_by_classes[parent]:
                        if parent_prop.property_ not in class_properties:
                            child_prop = parent_prop.model_copy(update={"class_": class_})
                            properties_by_classes[class_].append(child_prop)
                            class_properties.add(child_prop.property_)

        return properties_by_classes

    def implements_by_view(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ViewEntity, set[ViewEntity]]:
        """Get a dictionary of views and their implemented views."""
        # This is a duplicate fo the parent_by_class method, but for views
        # The choice to duplicate the code is to avoid generics which will make the code less readable
        implements_by_view: dict[ViewEntity, set[ViewEntity]] = {}
        for view in self.dms.views:
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
    ) -> dict[ViewEntity, list[DMSProperty]]:
        """Get a dictionary of views and their properties."""
        # This is a duplicate fo the properties_by_class method, but for views
        # The choice to duplicate the code is to avoid generics which will make the code less readable.
        properties_by_views: dict[ViewEntity, list[DMSProperty]] = defaultdict(list)
        for prop in self.dms.properties:
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
    def logical_uri_by_view(self) -> dict[ViewEntity, URIRef]:
        """Get the logical URI by view."""
        return {view.view: view.logical for view in self.dms.views if view.logical}

    def logical_uri_by_property_by_view(
        self,
        include_ancestors: bool = False,
        include_different_space: bool = False,
    ) -> dict[ViewEntity, dict[str, URIRef]]:
        """Get the logical URI by property by view."""
        properties_by_view = self.properties_by_view(include_ancestors, include_different_space)

        return {
            view: {prop.view_property: prop.logical for prop in properties if prop.logical}
            for view, properties in properties_by_view.items()
        }

    @property
    def _class_by_neat_id(self) -> dict[URIRef, InformationClass]:
        """Get a dictionary of class neat IDs to
        class entities."""

        return {cls.neatId: cls for cls in self.information.classes if cls.neatId}

    def class_by_suffix(self) -> dict[str, InformationClass]:
        """Get a dictionary of class suffixes to class entities."""
        # TODO: Remove this method
        class_dict: dict[str, InformationClass] = {}
        for definition in self.information.classes:
            entity = definition.class_
            if entity.suffix in class_dict:
                warnings.warn(
                    NeatValueWarning(
                        f"Class {entity} has been defined more than once! Only the first definition "
                        "will be considered, skipping the rest.."
                    ),
                    stacklevel=2,
                )
                continue
            class_dict[entity.suffix] = definition
        return class_dict

    @property
    def class_by_class_entity(self) -> dict[ClassEntity, InformationClass]:
        """Get a dictionary of class entities to class entities."""
        rules = self.information
        return {cls.class_: cls for cls in rules.classes}

    @property
    def view_by_view_entity(self) -> dict[ViewEntity, DMSView]:
        """Get a dictionary of class entities to class entities."""
        rules = self.dms
        return {view.view: view for view in rules.views}

    def property_by_id(self) -> dict[str, list[InformationProperty]]:
        """Get a dictionary of property IDs to property entities."""
        property_dict: dict[str, list[InformationProperty]] = defaultdict(list)
        for prop in self.information.properties:
            property_dict[prop.property_].append(prop)
        return property_dict

    def properties_by_id_by_class(
        self,
        has_instance_source: bool = False,
        include_ancestors: bool = False,
    ) -> dict[ClassEntity, dict[str, InformationProperty]]:
        """Get a dictionary of class entities to dictionaries of property IDs to property entities."""
        class_property_pairs: dict[ClassEntity, dict[str, InformationProperty]] = {}
        for class_, properties in self.properties_by_class(include_ancestors).items():
            processed_properties: dict[str, InformationProperty] = {}
            for prop in properties:
                if prop.property_ in processed_properties:
                    warnings.warn(
                        NeatValueWarning(
                            f"Property {processed_properties} for {class_} has been defined more than once!"
                            " Only the first definition will be considered, skipping the rest.."
                        ),
                        stacklevel=2,
                    )
                    continue
                if has_instance_source and prop.instance_source is None:
                    continue
                processed_properties[prop.property_] = prop
            class_property_pairs[class_] = processed_properties

        return class_property_pairs

    def defined_views(self, include_ancestors: bool = False) -> set[ViewEntity]:
        properties_by_view = self.properties_by_view(include_ancestors)
        return {prop.view for prop in itertools.chain.from_iterable(properties_by_view.values())}

    def defined_classes(
        self,
        include_ancestors: bool = False,
    ) -> set[ClassEntity]:
        """Returns classes that have properties defined for them in the data model.

        Args:
            include_ancestors: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that have been defined in the data model
        """
        properties_by_class = self.properties_by_class(include_ancestors)
        return {prop.class_ for prop in itertools.chain.from_iterable(properties_by_class.values())}

    def class_linkage(
        self,
        include_ancestors: bool = False,
    ) -> LinkageSet:
        """Returns a set of class linkages in the data model.

        Args:
            include_ancestors: Whether to consider inheritance or not. Defaults False

        Returns:

        """
        class_linkage = LinkageSet()

        properties_by_class = self.properties_by_class(include_ancestors)

        prop: InformationProperty
        for prop in itertools.chain.from_iterable(properties_by_class.values()):
            if not isinstance(prop.value_type, ClassEntity):
                continue
            class_linkage.add(
                Linkage(
                    source_class=prop.class_,
                    connecting_property=prop.property_,
                    target_class=prop.value_type,
                    max_occurrence=prop.max_count,
                )
            )

        return class_linkage

    def symmetrically_connected_classes(
        self,
        include_ancestors: bool = False,
    ) -> set[tuple[ClassEntity, ClassEntity]]:
        """Returns a set of pairs of symmetrically linked classes.

        Args:
            include_ancestors: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of pairs of symmetrically linked classes

        !!! note "Symmetrically Connected Classes"
            Symmetrically connected classes are classes that are connected to each other
            in both directions. For example, if class A is connected to class B, and class B
            is connected to class A, then classes A and B are symmetrically connected.
        """
        sym_pairs: set[tuple[ClassEntity, ClassEntity]] = set()
        class_linkage = self.class_linkage(include_ancestors)
        if not class_linkage:
            return sym_pairs

        targets_by_source = class_linkage.get_target_classes_by_source()
        for link in class_linkage:
            source = link.source_class
            target = link.target_class

            if source in targets_by_source[source] and (source, target) not in sym_pairs:
                sym_pairs.add((source, target))
        return sym_pairs

    @overload
    def _properties_by_neat_id(self, format: Literal["info"] = "info") -> dict[URIRef, InformationProperty]: ...

    @overload
    def _properties_by_neat_id(self, format: Literal["dms"] = "dms") -> dict[URIRef, DMSProperty]: ...

    def _properties_by_neat_id(
        self, format: Literal["info", "dms"] = "info"
    ) -> dict[URIRef, InformationProperty] | dict[URIRef, DMSProperty]:
        if format == "info":
            return {prop.neatId: prop for prop in self.information.properties if prop.neatId}
        elif format == "dms":
            return {prop.neatId: prop for prop in self.dms.properties if prop.neatId}
        else:
            raise NeatValueError(f"Invalid format: {format}")

    @property
    def classes_by_neat_id(self) -> dict[URIRef, InformationClass]:
        return {class_.neatId: class_ for class_ in self.information.classes if class_.neatId}

    @property
    def multi_value_properties(self) -> list[InformationProperty]:
        return [prop_ for prop_ in self.information.properties if isinstance(prop_.value_type, MultiValueTypeInfo)]

    @property
    def view_query_by_id(
        self,
    ) -> "ViewQueryDict":
        # Trigger error if any of these are missing
        _ = self.information
        _ = self.dms

        # caching results for faster access
        classes_by_neat_id = self._class_by_neat_id
        properties_by_class = self.properties_by_class(include_ancestors=True)
        logical_uri_by_view = self.logical_uri_by_view
        logical_uri_by_property_by_view = self.logical_uri_by_property_by_view(include_ancestors=True)
        information_properties_by_neat_id = self._properties_by_neat_id()

        query_configs = ViewQueryDict()
        for view in self.dms.views:
            # this entire block of sequential if statements checks:
            # 1. connection of dms to info rules
            # 2. correct paring of information and dms rules
            # 3. connection of info rules to instances
            if (
                (neat_id := logical_uri_by_view.get(view.view))
                and (class_ := classes_by_neat_id.get(neat_id))
                and (uri := class_.instance_source)
            ):
                view_query = ViewQuery(
                    view_id=view.view.as_id(),
                    rdf_type=uri,
                    # start off with renaming of properties on the information level
                    # this is to encounter for special cases of e.g. space, startNode and endNode
                    property_renaming_config=(
                        {uri: prop_.property_ for prop_ in info_properties for uri in prop_.instance_source or []}
                        if (info_properties := properties_by_class.get(class_.class_))
                        else {}
                    ),
                )

                if logical_uri_by_property := logical_uri_by_property_by_view.get(view.view):
                    for target_name, neat_id in logical_uri_by_property.items():
                        if (property_ := information_properties_by_neat_id.get(neat_id)) and (
                            uris := property_.instance_source
                        ):
                            for uri in uris:
                                view_query.property_renaming_config[uri] = target_name

                query_configs[view.view.as_id()] = view_query

        return query_configs

    def _dms_di_graph(self, format: Literal["data-model", "implements"] = "data-model") -> nx.MultiDiGraph:
        """Generate a MultiDiGraph from the DMS rules."""
        di_graph = nx.MultiDiGraph()

        rules = self.dms

        # Add nodes and edges from Views sheet
        for view in rules.views:
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
            for prop_ in rules.properties:
                if prop_.connection and isinstance(prop_.value_type, ViewEntity):
                    di_graph.add_node(prop_.view.suffix, label=prop_.view.suffix)
                    di_graph.add_node(prop_.value_type.suffix, label=prop_.value_type.suffix)
                    di_graph.add_edge(
                        prop_.view.suffix,
                        prop_.value_type.suffix,
                        label=prop_.name or prop_.view_property,
                    )

        return di_graph

    def _info_di_graph(self, format: Literal["data-model", "implements"] = "data-model") -> nx.MultiDiGraph:
        """Generate MultiDiGraph representing information data model."""

        rules = self.information
        di_graph = nx.MultiDiGraph()

        # Add nodes and edges from Views sheet
        for class_ in rules.classes:
            # if possible use human readable label coming from the view name

            di_graph.add_node(
                class_.class_.suffix,
                label=class_.name or class_.class_.suffix,
            )

            if format == "implements" and class_.implements:
                for parent in class_.implements:
                    di_graph.add_node(parent.suffix, label=parent.suffix)
                    di_graph.add_edge(
                        class_.class_.suffix,
                        parent.suffix,
                        label="implements",
                        dashes=True,
                    )

        if format == "data-model":
            # Add nodes and edges from Properties sheet
            for prop_ in rules.properties:
                if isinstance(prop_.value_type, ClassEntity) and not isinstance(prop_.value_type, UnknownEntity):
                    di_graph.add_node(prop_.class_.suffix, label=prop_.class_.suffix)
                    di_graph.add_node(prop_.value_type.suffix, label=prop_.value_type.suffix)

                    di_graph.add_edge(
                        prop_.class_.suffix,
                        prop_.value_type.suffix,
                        label=prop_.name or prop_.property_,
                    )

        return di_graph
