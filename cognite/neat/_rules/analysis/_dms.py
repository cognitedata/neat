from collections import defaultdict

from rdflib import URIRef

from cognite.neat._constants import DMS_LISTABLE_PROPERTY_LIMIT
from cognite.neat._rules.models.dms import DMSProperty, DMSRules, DMSView
from cognite.neat._rules.models.entities import ViewEntity

from ._base import BaseAnalysis


class DMSAnalysis(BaseAnalysis[DMSRules, DMSView, DMSProperty, ViewEntity, str]):
    """Assumes analysis over only the complete schema"""

    def _get_classes(self) -> list[DMSView]:
        return list(self.rules.views)

    def _get_properties(self) -> list[DMSProperty]:
        return list(self.rules.properties)

    def _get_cls_entity(self, class_: DMSView | DMSProperty) -> ViewEntity:
        return class_.view

    def _get_cls_parents(self, class_: DMSView) -> list[ViewEntity] | None:
        return list(class_.implements) if class_.implements else None

    @classmethod
    def _set_cls_entity(cls, property_: DMSProperty, class_: ViewEntity) -> None:
        property_.view = class_

    def _get_object(self, property_: DMSProperty) -> ViewEntity | None:
        return property_.value_type if isinstance(property_.value_type, ViewEntity) else None

    def _get_max_occurrence(self, property_: DMSProperty) -> int | float | None:
        return DMS_LISTABLE_PROPERTY_LIMIT if property_.is_list else 1

    def subset_rules(self, desired_classes: set[ViewEntity]) -> DMSRules:
        raise NotImplementedError()

    def _get_prop_entity(self, property_: DMSProperty) -> str:
        return property_.view_property

    def views_with_properties_linked_to_classes(
        self,
        consider_inheritance: bool = False,
        allow_different_namespace: bool = False,
    ) -> dict[ViewEntity, dict[str, URIRef]]:
        view_property_pairs = self.classes_with_properties(consider_inheritance, allow_different_namespace)

        view_and_properties_with_links: dict[ViewEntity, dict[str, URIRef]] = defaultdict(dict)

        for view, properties in view_property_pairs.items():
            view_and_properties_with_links[view] = {
                prop.view_property: prop.logical for prop in properties if prop.logical
            }

        return view_and_properties_with_links
