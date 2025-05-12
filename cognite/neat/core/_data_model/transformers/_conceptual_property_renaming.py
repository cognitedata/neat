from cognite.neat.core._data_model.models import ConceptualDataModel
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer


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
        raise NotImplementedError()
