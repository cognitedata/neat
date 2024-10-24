import itertools
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Set
from dataclasses import dataclass
from typing import Generic, TypeVar

import pandas as pd
from pydantic import BaseModel

from cognite.neat._rules.models._base_rules import BaseRules
from cognite.neat._rules.models._rdfpath import RDFPath
from cognite.neat._rules.models.entities import (
    ClassEntity,
    Entity,
    ReferenceEntity,
)
from cognite.neat._rules.models.information import InformationProperty
from cognite.neat._utils.rdf_ import get_inheritance_path

T_Rules = TypeVar("T_Rules", bound=BaseRules)
T_Property = TypeVar("T_Property", bound=BaseModel)
T_Class = TypeVar("T_Class", bound=BaseModel)
T_ClassEntity = TypeVar("T_ClassEntity", bound=Entity)
T_PropertyEntity = TypeVar("T_PropertyEntity", bound=Entity | str)


@dataclass(frozen=True)
class Linkage(Generic[T_ClassEntity, T_PropertyEntity]):
    source_class: T_ClassEntity
    connecting_property: T_PropertyEntity
    target_class: T_ClassEntity
    max_occurrence: int | float | None


class LinkageSet(set, Generic[T_ClassEntity, T_PropertyEntity], Set[Linkage[T_ClassEntity, T_PropertyEntity]]):
    @property
    def source_class(self) -> set[T_ClassEntity]:
        return {link.source_class for link in self}

    @property
    def target_class(self) -> set[T_ClassEntity]:
        return {link.target_class for link in self}

    def get_target_classes_by_source(self) -> dict[T_ClassEntity, set[T_ClassEntity]]:
        target_classes_by_source: dict[T_ClassEntity, set[T_ClassEntity]] = defaultdict(set)
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


class BaseAnalysis(ABC, Generic[T_Rules, T_Class, T_Property, T_ClassEntity, T_PropertyEntity]):
    def __init__(self, rules: T_Rules) -> None:
        self.rules = rules

    @abstractmethod
    def _get_classes(self) -> list[T_Class]:
        raise NotImplementedError

    @abstractmethod
    def _get_properties(self) -> list[T_Property]:
        raise NotImplementedError

    @abstractmethod
    def _get_reference(self, class_or_property: T_Class | T_Property) -> ReferenceEntity | None:
        raise NotImplementedError

    @abstractmethod
    def _get_cls_entity(self, class_: T_Class | T_Property) -> T_ClassEntity:
        raise NotImplementedError

    @abstractmethod
    def _get_prop_entity(self, property_: T_Property) -> T_PropertyEntity:
        raise NotImplementedError

    @abstractmethod
    def _get_cls_parents(self, class_: T_Class) -> list[T_ClassEntity] | None:
        raise NotImplementedError

    @abstractmethod
    def _get_reference_rules(self) -> T_Rules | None:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def _set_cls_entity(cls, property_: T_Property, class_: T_ClassEntity) -> None:
        raise NotImplementedError

    @abstractmethod
    def _get_object(self, property_: T_Property) -> T_ClassEntity | None:
        raise NotImplementedError

    @abstractmethod
    def _get_max_occurrence(self, property_: T_Property) -> int | float | None:
        raise NotImplementedError

    @property
    def directly_referred_classes(self) -> set[ClassEntity]:
        ref_rules = self._get_reference_rules()
        if ref_rules is None:
            return set()
        prefix = ref_rules.metadata.get_prefix()
        return {
            ref.as_class_entity()
            for class_ in self._get_classes()
            if isinstance((ref := self._get_reference(class_)), ReferenceEntity) and ref.prefix == prefix
        }

    @property
    def inherited_referred_classes(self) -> set[ClassEntity]:
        dir_referred_classes = self.directly_referred_classes
        inherited_referred_classes = []
        for class_ in dir_referred_classes:
            inherited_referred_classes.extend(self.class_inheritance_path(class_))
        return set(inherited_referred_classes)

    # Todo Lru cache this method.
    def class_parent_pairs(self) -> dict[T_ClassEntity, list[T_ClassEntity]]:
        """This only returns class - parent pairs only if parent is in the same data model"""
        class_subclass_pairs: dict[T_ClassEntity, list[T_ClassEntity]] = {}
        for cls_ in self._get_classes():
            entity = self._get_cls_entity(cls_)
            class_subclass_pairs[entity] = []
            for parent in self._get_cls_parents(cls_) or []:
                if parent.prefix == entity.prefix:
                    class_subclass_pairs[entity].append(parent)
                else:
                    warnings.warn(
                        f"Parent class {parent} of class {cls_} is not in the same namespace, skipping !",
                        stacklevel=2,
                    )

        return class_subclass_pairs

    def classes_with_properties(self, consider_inheritance: bool = False) -> dict[T_ClassEntity, list[T_Property]]:
        """Returns classes that have been defined in the data model.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Dictionary of classes with a list of properties defined for them

        !!! note "consider_inheritance"
            If consider_inheritance is True, properties from parent classes will also be considered.
            This means if a class has a parent class, and the parent class has properties defined for it,
            while we do not have any properties defined for the child class, we will still consider the
            properties from the parent class. If consider_inheritance is False, we will only consider
            properties defined for the child class, thus if no properties are defined for the child class,
            it will not be included in the returned dictionary.
        """

        class_property_pairs: dict[T_ClassEntity, list[T_Property]] = defaultdict(list)

        for property_ in self._get_properties():
            class_property_pairs[self._get_cls_entity(property_)].append(property_)  # type: ignore

        if consider_inheritance:
            class_parent_pairs = self.class_parent_pairs()
            for class_ in class_parent_pairs:
                self._add_inherited_properties(class_, class_property_pairs, class_parent_pairs)

        return class_property_pairs

    def class_inheritance_path(self, class_: ClassEntity) -> list[ClassEntity]:
        class_parent_pairs = self.class_parent_pairs()
        return get_inheritance_path(class_, class_parent_pairs)

    @classmethod
    def _add_inherited_properties(
        cls,
        class_: T_ClassEntity,
        class_property_pairs: dict[T_ClassEntity, list[T_Property]],
        class_parent_pairs: dict[T_ClassEntity, list[T_ClassEntity]],
    ):
        inheritance_path = get_inheritance_path(class_, class_parent_pairs)
        for parent in inheritance_path:
            # ParentClassEntity -> ClassEntity to match the type of class_property_pairs
            if parent in class_property_pairs:
                for property_ in class_property_pairs[parent]:
                    property_ = property_.model_copy()

                    # This corresponds to importing properties from parent class
                    # making sure that the property is attached to desired child class
                    cls._set_cls_entity(property_, class_)

                    # need same if we have RDF path to make sure that the starting class is the
                    if class_ in class_property_pairs:
                        class_property_pairs[class_].append(property_)
                    else:
                        class_property_pairs[class_] = [property_]

    def class_property_pairs(
        self, only_rdfpath: bool = False, consider_inheritance: bool = False
    ) -> dict[T_ClassEntity, dict[T_PropertyEntity, T_Property]]:
        """Returns a dictionary of classes with a dictionary of properties associated with them.

        Args:
            only_rdfpath : To consider only properties which have rule `rdfpath` set. Defaults False
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Dictionary of classes with a dictionary of properties associated with them.

        !!! note "difference to get_classes_with_properties"
            This method returns a dictionary of classes with a dictionary of properties associated with them.
            While get_classes_with_properties returns a dictionary of classes with a list of
            properties defined for them,
            here we filter the properties based on the `only_rdfpath` parameter and only consider
            the first definition of a property if it is defined more than once.

        !!! note "only_rdfpath"
            If only_rdfpath is True, only properties with RuleType.rdfpath will be returned as
            a part of the dictionary of properties related to a class. Otherwise, all properties
            will be returned.

        !!! note "consider_inheritance"
            If consider_inheritance is True, properties from parent classes will also be considered.
            This means if a class has a parent class, and the parent class has properties defined for it,
            while we do not have any properties defined for the child class, we will still consider the
            properties from the parent class. If consider_inheritance is False, we will only consider
            properties defined for the child class, thus if no properties are defined for the child class,
            it will not be included in the returned dictionary.
        """
        # TODO: https://cognitedata.atlassian.net/jira/software/projects/NEAT/boards/893?selectedIssue=NEAT-78

        class_property_pairs: dict[T_ClassEntity, dict[T_PropertyEntity, T_Property]] = {}

        for class_, properties in self.classes_with_properties(consider_inheritance).items():
            processed_properties: dict[T_PropertyEntity, T_Property] = {}
            for property_ in properties:
                prop_entity = self._get_prop_entity(property_)
                if prop_entity in processed_properties:
                    # TODO: use appropriate Warning class from _exceptions.py
                    # if missing make one !
                    warnings.warn(
                        f"Property {processed_properties} for {class_} has been defined more than once!"
                        " Only the first definition will be considered, skipping the rest..",
                        stacklevel=2,
                    )
                    continue

                if (
                    only_rdfpath
                    and isinstance(property_, InformationProperty)
                    and isinstance(property_.transformation, RDFPath)
                ) or not only_rdfpath:
                    processed_properties[prop_entity] = property_
            class_property_pairs[class_] = processed_properties

        return class_property_pairs

    def class_linkage(self, consider_inheritance: bool = False) -> LinkageSet[T_ClassEntity, T_PropertyEntity]:
        """Returns a set of class linkages in the data model.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:

        """
        class_linkage = LinkageSet[T_ClassEntity, T_PropertyEntity]()

        class_property_pairs = self.classes_with_properties(consider_inheritance)
        properties = list(itertools.chain.from_iterable(class_property_pairs.values()))

        for property_ in properties:
            object_ = self._get_object(property_)
            if object_ is not None:
                class_linkage.add(
                    Linkage(
                        source_class=self._get_cls_entity(property_),
                        connecting_property=self._get_prop_entity(property_),
                        target_class=object_,
                        max_occurrence=self._get_max_occurrence(property_),
                    )
                )

        return class_linkage

    def connected_classes(self, consider_inheritance: bool = False) -> set[T_ClassEntity]:
        """Return a set of classes that are connected to other classes.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that are connected to other classes
        """
        class_linkage = self.class_linkage(consider_inheritance)
        return class_linkage.source_class.union(class_linkage.target_class)

    def defined_classes(self, consider_inheritance: bool = False) -> set[T_ClassEntity]:
        """Returns classes that have properties defined for them in the data model.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that have been defined in the data model
        """
        class_property_pairs = self.classes_with_properties(consider_inheritance)
        properties = list(itertools.chain.from_iterable(class_property_pairs.values()))

        return {self._get_cls_entity(property) for property in properties}

    def disconnected_classes(self, consider_inheritance: bool = False) -> set[T_ClassEntity]:
        """Return a set of classes that are disconnected (i.e. isolated) from other classes.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of classes that are disconnected from other classes
        """
        return self.defined_classes(consider_inheritance) - self.connected_classes(consider_inheritance)

    def symmetrically_connected_classes(
        self, consider_inheritance: bool = False
    ) -> set[tuple[ClassEntity, ClassEntity]]:
        """Returns a set of pairs of symmetrically linked classes.

        Args:
            consider_inheritance: Whether to consider inheritance or not. Defaults False

        Returns:
            Set of pairs of symmetrically linked classes

        !!! note "Symmetrically Connected Classes"
            Symmetrically connected classes are classes that are connected to each other
            in both directions. For example, if class A is connected to class B, and class B
            is connected to class A, then classes A and B are symmetrically connected.
        """

        # TODO: Find better name for this method
        sym_pairs: set[tuple[ClassEntity, ClassEntity]] = set()

        class_linkage = self.class_linkage(consider_inheritance)
        if not class_linkage:
            return sym_pairs

        targets_by_source = class_linkage.get_target_classes_by_source()
        for link in class_linkage:
            source = link.source_class
            target = link.target_class

            if source in targets_by_source[source] and (source, target) not in sym_pairs:
                sym_pairs.add((source, target))
        return sym_pairs

    def as_property_dict(
        self,
    ) -> dict[T_PropertyEntity, list[T_Property]]:
        """This is used to capture all definitions of a property in the data model."""
        property_dict: dict[T_PropertyEntity, list[T_Property]] = defaultdict(list)
        for definition in self._get_properties():
            property_dict[self._get_prop_entity(definition)].append(definition)
        return property_dict

    def as_class_dict(self) -> dict[str, T_Class]:
        """This is to simplify access to classes through dict."""
        class_dict: dict[str, T_Class] = {}
        for definition in self._get_classes():
            entity = self._get_cls_entity(definition)
            if entity.suffix in class_dict:
                warnings.warn(
                    f"Class {entity} has been defined more than once! Only the first definition "
                    "will be considered, skipping the rest..",
                    stacklevel=2,
                )
                continue
            class_dict[entity.suffix] = definition
        return class_dict

    @abstractmethod
    def subset_rules(self, desired_classes: set[T_ClassEntity]) -> T_Rules:
        raise NotImplementedError
