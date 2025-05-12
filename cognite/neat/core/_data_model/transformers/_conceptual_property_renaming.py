import warnings

from cognite.neat.core._data_model.models import ConceptualDataModel
from cognite.neat.core._data_model.models.entities import ClassEntity
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer
from cognite.neat.core._issues.warnings import NeatValueWarning


class ConceptualPropertyRenaming(VerifiedRulesTransformer[ConceptualDataModel, ConceptualDataModel]):
    """Maps properties and classes

    Args:
        property_mapping (dict[tuple[str, str], tuple[str, str]]): A mapping of properties to be renamed.
            The keys are tuples of (class_external_id, property_external_id) and the values are tuples of
            (new_class_external_id, new_property_external_id).
    """

    def __init__(self, property_mapping: dict[tuple[str, str], tuple[str, str]]):
        self.property_mapping = property_mapping

    def transform(self, rules: ConceptualDataModel) -> ConceptualDataModel:
        output_rules = rules.model_copy(deep=True)
        mapping = self._prepare_mapping(output_rules)

        for prop in output_rules.properties:
            identifier = prop.class_, prop.property_
            if identifier in mapping:
                new_class, new_property = mapping[identifier]
                prop.class_ = new_class
                prop.property_ = new_property
        return output_rules

    def _prepare_mapping(self, rules: ConceptualDataModel) -> dict[tuple[ClassEntity, str], tuple[ClassEntity, str]]:
        mapping: dict[tuple[ClassEntity, str], tuple[ClassEntity, str]] = {}
        available_properties = {(prop.class_.suffix, prop.property_) for prop in rules.properties}
        class_entity_by_external_id = {cls_.class_.suffix: cls_.class_ for cls_ in rules.classes}
        for (class_external_id, property_external_id), (
            new_class_external_id,
            new_property_external_id,
        ) in self.property_mapping.items():
            class_entity = class_entity_by_external_id.get(class_external_id)
            new_class_entity = class_entity_by_external_id.get(new_class_external_id)
            if not class_entity:
                warnings.warn(NeatValueWarning(f"Concept '{class_external_id}' not found in data model."), stacklevel=2)
                continue
            if not new_class_entity:
                warnings.warn(
                    NeatValueWarning(f"Concept '{new_class_external_id}' not found in data model."), stacklevel=2
                )
                continue
            if (class_external_id, property_external_id) not in available_properties:
                warnings.warn(
                    NeatValueWarning(f"Property '{property_external_id}' not found in concept '{class_external_id}'."),
                    stacklevel=2,
                )
                continue
            if (new_class_external_id, new_property_external_id) in available_properties:
                warnings.warn(
                    NeatValueWarning(
                        f"Property '{new_property_external_id}' already exists in concept '{new_class_external_id}'."
                    ),
                    stacklevel=2,
                )
                continue
            mapping[(class_entity, property_external_id)] = (new_class_entity, new_property_external_id)
        return mapping
