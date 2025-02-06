import warnings
from collections import defaultdict
from graphlib import TopologicalSorter

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models.dms import DMSProperty
from cognite.neat._rules.models.entities import ClassEntity, ViewEntity
from cognite.neat._rules.models.information import InformationProperty


class RuleAnalysis:
    def __init__(self, information: InformationRules | None, dms: DMSRules | None = None) -> None:
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
