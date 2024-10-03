from abc import ABC
from collections import defaultdict
from dataclasses import dataclass

from cognite.neat.constants import CORE_CDF_NAMESPACE
from cognite.neat.rules._shared import JustRules, OutRules
from cognite.neat.rules.models import DMSRules, InformationInputRules
from cognite.neat.rules.models.dms import DMSProperty
from cognite.neat.rules.models.entities import ClassEntity, ReferenceEntity
from cognite.neat.rules.models.information import InformationInputClass, InformationInputProperty
from cognite.neat.utils.rdf_ import remove_namespace_from_uri

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
        if solution.reference is not None:
            raise ValueError("Reference already exists")
        solution.reference = self.reference
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
                prop.reference = ReferenceEntity.from_entity(ref_prop.view, ref_prop.view_property)

        return JustRules(solution)


@dataclass
class PropertyMapping:
    source: InformationInputProperty
    target: InformationInputProperty


@dataclass
class ClassMapping:
    source: InformationInputClass
    target: InformationInputClass


@dataclass
class Mapping:
    properties: list[PropertyMapping]
    classes: list[ClassMapping]


class ClassicToCoreMapper(RulesTransformer[InformationInputRules, InformationInputRules]):
    def __init__(self, mapping: Mapping) -> None:
        self.mapping = mapping

    def transform(
        self, rules: InformationInputRules | OutRules[InformationInputRules]
    ) -> JustRules[InformationInputRules]:
        input_rules = self._to_rules(rules)

        target_prop_by_source = {
            (prop.source.class_, prop.source.property_): prop.target for prop in self.mapping.properties
        }
        target_cls_by_source = {cls.source.class_: cls.target for cls in self.mapping.classes}
        meta = input_rules.metadata
        classic = meta.prefix
        core = remove_namespace_from_uri(CORE_CDF_NAMESPACE)
        for prop in input_rules.properties:
            if (prop.class_, prop.property_) in target_prop_by_source:
                target = target_prop_by_source[(prop.class_, prop.property_)]
                source_cls = ClassEntity.load(prop.class_, prefix=classic)
                target_cls = ClassEntity.load(target.class_, prefix=core)
                prop.transformation = (
                    f"{source_cls!s}({classic}:{prop.property_})->{target_cls!s}({core}:{target.property_})"
                )
                prop.property_ = target.property_
                if prop.class_ in target_cls_by_source:
                    prop.class_ = target_cls_by_source[prop.class_].class_

        return JustRules(input_rules)
