import itertools
import warnings
from collections import defaultdict
from collections.abc import Hashable, ItemsView, Iterator, KeysView, MutableMapping, Set, ValuesView
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from typing import Any, Literal, TypeVar, cast, overload

import pandas as pd
from cognite.client import data_modeling as dm
from pydantic import ValidationError
from rdflib import URIRef

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models._rdfpath import Hop, RDFPath, SelfReferenceProperty, SingleProperty
from cognite.neat._rules.models.dms import DMSProperty
from cognite.neat._rules.models.entities import ClassEntity, MultiValueTypeInfo, ViewEntity
from cognite.neat._rules.models.information import InformationClass, InformationProperty
from cognite.neat._utils.collection_ import most_occurring_element
from cognite.neat._utils.rdf_ import get_inheritance_path

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
                if has_instance_source and not isinstance(prop.instance_source, RDFPath):
                    continue
                processed_properties[prop.property_] = prop
            class_property_pairs[class_] = processed_properties

        return class_property_pairs

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
        class_property_pairs = self.properties_by_class(include_ancestors)
        return {prop.class_ for prop in itertools.chain.from_iterable(class_property_pairs.values())}

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

    def subset_rules(self, include_classes: Set[ClassEntity]) -> InformationRules:
        """Subset rules to only include desired classes and their properties.

        Args:
            include_classes: Desired classes to include in the reduced data model

        Returns:
            Instance of InformationRules

        !!! note "Inheritance"
            If desired classes contain a class that is a subclass of another class(es), the parent class(es)
            will be included in the reduced data model as well even though the parent class(es) are
            not in the desired classes set. This is to ensure that the reduced data model is
            consistent and complete.

        !!! note "Partial Reduction"
            This method does not perform checks if classes that are value types of desired classes
            properties are part of desired classes. If a class is not part of desired classes, but it
            is a value type of a property of a class that is part of desired classes, derived reduced
            rules will be marked as partial.

        !!! note "Validation"
            This method will attempt to validate the reduced rules with custom validations.
            If it fails, it will return a partial rules with a warning message, validated
            only with base Pydantic validators.
        """
        class_as_dict = self.class_by_suffix()
        parents_by_class = self.parents_by_class()
        defined_classes = self.defined_classes(include_ancestors=True)

        possible_classes = defined_classes.intersection(include_classes)
        impossible_classes = include_classes - possible_classes

        # need to add all the parent classes of the desired classes to the possible classes
        parents: set[ClassEntity] = set()
        for class_ in possible_classes:
            parents = parents.union(
                {
                    parent
                    for parent in get_inheritance_path(
                        class_, {cls_: list(parents) for cls_, parents in parents_by_class.items()}
                    )
                }
            )
        possible_classes = possible_classes.union(parents)

        if not possible_classes:
            raise ValueError("None of the desired classes are defined in the data model!")

        if impossible_classes:
            warnings.warn(
                f"Could not find the following classes defined in the data model: {impossible_classes}",
                stacklevel=2,
            )

        reduced_data_model: dict[str, Any] = {
            "metadata": self.information.metadata.model_copy(),
            "prefixes": (self.information.prefixes or {}).copy(),
            "classes": [],
            "properties": [],
        }

        for class_ in possible_classes:
            reduced_data_model["classes"].append(class_as_dict[str(class_.suffix)])

        class_property_pairs = self.properties_by_class(include_ancestors=False)

        for class_, properties in class_property_pairs.items():
            if class_ in possible_classes:
                reduced_data_model["properties"].extend(properties)

        try:
            return InformationRules.model_validate(reduced_data_model)
        except ValidationError as e:
            warnings.warn(f"Reduced data model is not complete: {e}", stacklevel=2)
            return InformationRules.model_construct(**reduced_data_model)

    def has_hop_transformations(self):
        return any(
            prop_.instance_source and isinstance(prop_.instance_source.traversal, Hop)
            for prop_ in self.information.properties
        )

    def has_self_reference_property_transformations(self):
        return any(
            prop_.instance_source and isinstance(prop_.instance_source.traversal, SelfReferenceProperty)
            for prop_ in self.information.properties
        )

    def define_property_renaming_config(self, class_: ClassEntity) -> dict[str | URIRef, str]:
        property_renaming_configuration: dict[str | URIRef, str] = {}

        if definitions := self.properties_by_id_by_class(has_instance_source=True, include_ancestors=True).get(class_):
            for property_id, definition in definitions.items():
                transformation = cast(RDFPath, definition.instance_source)
                # use case we have a single property rdf path, and defined prefix
                # in either metadata or prefixes of rules
                if isinstance(
                    transformation.traversal,
                    SingleProperty,
                ) and (
                    transformation.traversal.property.prefix in self.information.prefixes
                    or transformation.traversal.property.prefix == self.information.metadata.prefix
                ):
                    namespace = (
                        self.information.metadata.namespace
                        if transformation.traversal.property.prefix == self.information.metadata.prefix
                        else self.information.prefixes[transformation.traversal.property.prefix]
                    )

                    property_renaming_configuration[namespace[transformation.traversal.property.suffix]] = property_id

                # otherwise we default to the property id
                else:
                    property_renaming_configuration[property_id] = property_id

        return property_renaming_configuration

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

    def neat_id_to_instance_source_property_uri(self, property_neat_id: URIRef) -> URIRef | None:
        if (
            (property_ := self._properties_by_neat_id().get(property_neat_id))
            and property_.instance_source
            and isinstance(
                property_.instance_source.traversal,
                SingleProperty,
            )
            and (
                property_.instance_source.traversal.property.prefix in self.information.prefixes
                or property_.instance_source.traversal.property.prefix == self.information.metadata.prefix
            )
        ):
            namespace = (
                self.information.metadata.namespace
                if property_.instance_source.traversal.property.prefix == self.information.metadata.prefix
                else self.information.prefixes[property_.instance_source.traversal.property.prefix]
            )

            return namespace[property_.instance_source.traversal.property.suffix]
        return None

    def most_occurring_class_in_transformations(self, class_: ClassEntity) -> ClassEntity | None:
        classes = []
        if class_property_pairs := self.properties_by_id_by_class(include_ancestors=True, has_instance_source=True).get(
            class_
        ):
            for property_ in class_property_pairs.values():
                classes.append(cast(RDFPath, property_.instance_source).traversal.class_)

            return cast(ClassEntity, most_occurring_element(classes))
        else:
            return None

    def class_uri(self, class_: ClassEntity) -> URIRef | None:
        """Get URI for a class entity based on the rules.

        Args:
            class_: instance of ClassEntity

        Returns:
            URIRef of the class entity or None if not found
        """

        # we need to handle optional renamings and we do this
        # by checking if the most occurring class in transformations alternatively
        # in cases when we are not specifying transformations we default to the class entity
        if not (most_frequent_class := self.most_occurring_class_in_transformations(class_)):
            most_frequent_class = class_

        # case 1 class prefix in rules.prefixes
        if most_frequent_class.prefix in self.information.prefixes:
            return self.information.prefixes[cast(str, most_frequent_class.prefix)][most_frequent_class.suffix]

        # case 2 class prefix equal to rules.metadata.prefix
        elif most_frequent_class.prefix == self.information.metadata.prefix:
            return self.information.metadata.namespace[most_frequent_class.suffix]

        # case 3 when class prefix is not found in prefixes of rules
        else:
            return None

    def property_uri(self, property_: InformationProperty) -> URIRef | None:
        if (instance_source := property_.instance_source) and isinstance(instance_source.traversal, SingleProperty):
            prefix = instance_source.traversal.property.prefix
            suffix = instance_source.traversal.property.suffix

            if namespace := self.information.prefixes.get(prefix):
                return namespace[suffix]
        return None

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
                and (uri := self.class_uri(class_.class_))
            ):
                view_query = ViewQuery(
                    view_id=view.view.as_id(),
                    rdf_type=uri,
                    # start off with renaming of properties on the information level
                    # this is to encounter for special cases of e.g. space, startNode and endNode
                    property_renaming_config=(
                        {uri: prop_.property_ for prop_ in info_properties if (uri := self.property_uri(prop_))}
                        if (info_properties := properties_by_class.get(class_.class_))
                        else {}
                    ),
                )

                if logical_uri_by_property := logical_uri_by_property_by_view.get(view.view):
                    for target_name, neat_id in logical_uri_by_property.items():
                        if (property_ := information_properties_by_neat_id.get(neat_id)) and (
                            uri := self.property_uri(property_)
                        ):
                            view_query.property_renaming_config[uri] = target_name

                query_configs[view.view.as_id()] = view_query

        return query_configs
