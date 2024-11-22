import warnings
from abc import ABC
from collections import defaultdict
from typing import Literal

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import PropertyOverwritingValueTypeWarning
from cognite.neat._rules._shared import JustRules, OutRules
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.dms import DMSProperty, DMSView
from cognite.neat._rules.models.entities import ViewEntity
from cognite.neat._rules.models.mapping import RuleMapping

from ._base import RulesTransformer


class MapOntoTransformers(RulesTransformer[DMSRules, DMSRules], ABC):
    """Base class for transformers that map one rule onto another."""

    ...


class MapOneToOne(MapOntoTransformers):
    """Takes transform data models and makes it into an extension of the reference data model.

    Note this transformer mutates the input rules.

    The argument view_extension_mapping is a dictionary where the keys are views of this data model,
    and each value is the view of the reference data model that the view should extend. For example:

    ```python
    view_extension_mapping = {"Pump": "Asset"}
    ```

    This would make the view "Pump" in this data model extend the view "Asset" in the reference data model.
    Note that all the keys in the dictionary must be external ids of views in this data model,
    and all the values must be external ids of views in the reference data model.

    Args:
        reference: The reference data model
        view_extension_mapping: A dictionary mapping views in this data model to views in the reference data model
        default_extension: The default view in the reference data model that views in this
            data model should extend if no mapping is provided.

    """

    def __init__(
        self, reference: DMSRules, view_extension_mapping: dict[str, str], default_extension: str | None = None
    ) -> None:
        self.reference = reference
        self.view_extension_mapping = view_extension_mapping
        self.default_extension = default_extension

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        solution: DMSRules = self._to_rules(rules)
        view_by_external_id = {view.view.external_id: view for view in solution.views}
        ref_view_by_external_id = {view.view.external_id: view for view in self.reference.views}

        if invalid_views := set(self.view_extension_mapping.keys()) - set(view_by_external_id.keys()):
            raise ValueError(f"Views are not in this dat model {invalid_views}")
        if invalid_views := set(self.view_extension_mapping.values()) - set(ref_view_by_external_id.keys()):
            raise ValueError(f"Views are not in the reference data model {invalid_views}")
        if self.default_extension and self.default_extension not in ref_view_by_external_id:
            raise ValueError(f"Default extension view not in the reference data model {self.default_extension}")

        properties_by_view_external_id: dict[str, dict[str, DMSProperty]] = defaultdict(dict)
        for prop in solution.properties:
            properties_by_view_external_id[prop.view.external_id][prop.view_property] = prop

        ref_properties_by_view_external_id: dict[str, dict[str, DMSProperty]] = defaultdict(dict)
        for prop in self.reference.properties:
            ref_properties_by_view_external_id[prop.view.external_id][prop.view_property] = prop

        for view_external_id, view in view_by_external_id.items():
            if view_external_id in self.view_extension_mapping:
                ref_external_id = self.view_extension_mapping[view_external_id]
            elif self.default_extension:
                ref_external_id = self.default_extension
            else:
                continue

            ref_view = ref_view_by_external_id[ref_external_id]
            shared_properties = set(properties_by_view_external_id[view_external_id].keys()) & set(
                ref_properties_by_view_external_id[ref_external_id].keys()
            )
            if shared_properties:
                if view.implements is None:
                    view.implements = [ref_view.view]
                elif isinstance(view.implements, list) and ref_view.view not in view.implements:
                    view.implements.append(ref_view.view)
            for prop_name in shared_properties:
                prop = properties_by_view_external_id[view_external_id][prop_name]
                ref_prop = ref_properties_by_view_external_id[ref_external_id][prop_name]
                if ref_prop.container and ref_prop.container_property:
                    prop.container = ref_prop.container
                    prop.container_property = ref_prop.container_property

        return JustRules(solution)


class RuleMapper(RulesTransformer[DMSRules, DMSRules]):
    """Maps properties and classes using the given mapping.

    **Note**: This transformer mutates the input rules.

    Args:
        mapping: The mapping to use.

    """

    def __init__(self, mapping: RuleMapping, data_type_conflict: Literal["overwrite"] = "overwrite") -> None:
        self.mapping = mapping
        self.data_type_conflict = data_type_conflict

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        if self.data_type_conflict != "overwrite":
            raise NeatValueError(f"Invalid data_type_conflict: {self.data_type_conflict}")
        input_rules = self._to_rules(rules)
        new_rules = input_rules.model_copy(deep=True)

        destination_prop_by_source = self.mapping.properties.as_destination_by_source()
        for prop in new_rules.properties:
            ref = prop.as_container_reference()
            if destination_prop := destination_prop_by_source.get(ref):
                if prop.value_type != destination_prop.value_type and self.data_type_conflict == "overwrite":
                    warnings.warn(
                        PropertyOverwritingValueTypeWarning(
                            ref.container,
                            "container",
                            ref.property_,  # type: ignore[arg-type]
                            value_type=str(prop.value_type),
                            overwrite_value_type=str(destination_prop.value_type),
                        ),
                        stacklevel=2,
                    )
                    prop.value_type = destination_prop.value_type
                prop.container = destination_prop.container
                prop.container_property = destination_prop.property_

        destination_view_by_source = self.mapping.views.as_destination_by_source()
        used_views: set[ViewEntity] = set()
        for view in new_rules.views:
            if destination_view := destination_view_by_source.get(view.as_view_reference()):
                view.implements = [destination_view.view]
                used_views.add(destination_view.view)

        existing_views = {view.view for view in input_rules.views}
        for new_view in list(used_views - existing_views):
            new_rules.views.append(
                DMSView(
                    view=new_view,
                    in_model=True,
                )
            )

        return JustRules(new_rules)
