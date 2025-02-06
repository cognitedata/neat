import warnings
from collections import defaultdict
from graphlib import TopologicalSorter

from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationProperty


class RuleAnalysis:
    def __init__(self, information: InformationRules, dms: DMSRules | None = None) -> None:
        self._information = information
        self._dms = dms

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
        for class_ in self._information.classes:
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
        for prop in self._information.properties:
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
