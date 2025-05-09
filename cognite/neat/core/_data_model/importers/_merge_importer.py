from cognite.neat.core._data_model._shared import InputRules, ReadRules
from cognite.neat.core._data_model.models import DMSInputRules, DMSRules, InformationInputRules, InformationRules
from cognite.neat.core._issues.errors import NeatValueError

from ._base import BaseImporter


class DMSMergeImporter(BaseImporter):
    """Merges two importers into data model one.
    Args:
        existing: The existing data model.
        additional: The additional data model to merge.
    """

    def __init__(self, existing: ReadRules[InputRules], additional: ReadRules[InputRules]):
        self.existing = existing
        self.additional = additional

    @property
    def description(self) -> str:
        return "Merges two data models into one."

    @classmethod
    def from_importers(cls, existing: BaseImporter, additional: BaseImporter) -> "DMSMergeImporter":
        return cls(existing.to_rules(), additional.to_rules())

    def to_rules(self) -> ReadRules[DMSInputRules]:
        # Local import to avoid circular import
        from cognite.neat.core._data_model.transformers._converters import MergeDMSRules

        existing_dms = self._get_dms_model(self.existing.rules, "Existing")
        additional_dms = self._get_dms_model(self.additional.rules, "Additional")
        merged = MergeDMSRules(additional_dms).transform(existing_dms)

        return ReadRules(
            rules=DMSInputRules.load(merged.dump()),
            read_context=self.additional.read_context or self.existing.read_context,
        )

    @staticmethod
    def _get_dms_model(input_model: InformationInputRules | DMSInputRules | None, name: str) -> DMSRules:
        # Local import to avoid circular import
        from cognite.neat.core._data_model.transformers import InformationToDMS

        if input_model is None:
            raise NeatValueError(f"Cannot merge. {name} data model failed read.")

        verified_model = input_model.as_verified_rules()
        if isinstance(verified_model, DMSRules):
            return verified_model
        elif isinstance(verified_model, InformationRules):
            return InformationToDMS().transform(verified_model)
        else:
            raise NeatValueError(f"Cannot merge. {name} data model is not a DMS or Information data model")
