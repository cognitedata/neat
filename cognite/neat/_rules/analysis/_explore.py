import itertools
import warnings
from collections import defaultdict
from graphlib import TopologicalSorter

from rdflib import URIRef

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models._rdfpath import RDFPath
from cognite.neat._rules.models.dms import DMSProperty
from cognite.neat._rules.models.entities import ClassEntity, ViewEntity
from cognite.neat._rules.models.information import InformationClass, InformationProperty


class RuleAnalysis:
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
            # Topological sort to ensure that classes include all ancestors
            for class_entity in list(TopologicalSorter(parents_by_class).static_order()):
                parents_by_class[class_entity] |= {
                    grand_parent
                    for parent in parents_by_class[class_entity]
                    for grand_parent in parents_by_class[parent]
                }

        return parents_by_class

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
        properties_by_classes = defaultdict(list)
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
                            properties_by_classes[class_].append(parent_prop)
                            class_properties.add(parent_prop.property_)

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
            # Topological sort to ensure that views include all ancestors
            for view_entity in list(TopologicalSorter(implements_by_view).static_order()):
                implements_by_view[view_entity] |= {
                    grand_parent
                    for parent in implements_by_view[view_entity]
                    for grand_parent in implements_by_view[parent]
                }
        return implements_by_view

    def properties_by_view(
        self, include_ancestors: bool = False, include_different_space: bool = False
    ) -> dict[ViewEntity, list[DMSProperty]]:
        """Get a dictionary of views and their properties."""
        # This is a duplicate fo the properties_by_class method, but for views
        # The choice to duplicate the code is to avoid generics which will make the code less readable.
        properties_by_views = defaultdict(list)
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
                            properties_by_views[view].append(parent_prop)
                            view_properties.add(parent_prop.view_property)

        return properties_by_views

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
