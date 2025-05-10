from cognite.neat.core._data_model.models import InformationRules
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer


class MergeInformationRules(VerifiedRulesTransformer[InformationRules, InformationRules]):
    def __init__(self, extra: InformationRules) -> None:
        self.extra = extra

    def transform(self, rules: InformationRules) -> InformationRules:
        output = rules.model_copy(deep=True)
        existing_classes = {cls.class_ for cls in output.classes}
        for cls in self.extra.classes:
            if cls.class_ not in existing_classes:
                output.classes.append(cls)
        existing_properties = {(prop.class_, prop.property_) for prop in output.properties}
        for prop in self.extra.properties:
            if (prop.class_, prop.property_) not in existing_properties:
                output.properties.append(prop)
        for prefix, namespace in self.extra.prefixes.items():
            if prefix not in output.prefixes:
                output.prefixes[prefix] = namespace
        return output
