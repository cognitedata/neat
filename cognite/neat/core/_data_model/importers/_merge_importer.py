from cognite.neat.core._client import NeatClient
from cognite.neat.core._data_model._shared import ReadRules
from cognite.neat.core._data_model.models import DMSInputRules, DMSRules, InformationInputRules, InformationRules
from cognite.neat.core._issues.errors import NeatValueError

from ._base import BaseImporter


class DMSMergeImporter(BaseImporter):
    """Merges two importers into data model one.
    Args:
        existing: The existing data model.
        additional: The additional data model to merge.
    """

    def __init__(self, existing: BaseImporter, additional: BaseImporter, client: NeatClient | None = None):
        self.existing = existing
        self.additional = additional
        self.client = client

    @property
    def description(self) -> str:
        return "Merges two data models into one."

    def to_rules(self) -> ReadRules[DMSInputRules]:
        # Local import to avoid circular import
        from cognite.neat.core._data_model.transformers import MergeDMSRules

        existing_input = self.existing.to_rules()
        existing_dms = self._get_dms_model(existing_input.rules, "Existing")
        additional_input = self.additional.to_rules()
        additional_dms = self._get_dms_model(additional_input.rules, "Additional")
        if additional_dms.metadata.identifier != existing_dms.metadata.identifier:
            raise NeatValueError("Cannot merge. The identifiers of the two data models do not match.")
        merged = MergeDMSRules(additional_dms).transform(existing_dms)

        return ReadRules(
            rules=DMSInputRules.load(merged.dump()),
            read_context=additional_input.read_context or existing_input.read_context,
        )

    def _get_dms_model(self, input_model: InformationInputRules | DMSInputRules | None, name: str) -> DMSRules:
        # Local import to avoid circular import
        from cognite.neat.core._data_model.transformers import InformationToDMS

        if input_model is None:
            raise NeatValueError(f"Cannot merge. {name} data model failed read.")

        verified_model = input_model.as_verified_rules()
        if isinstance(verified_model, DMSRules):
            return verified_model
        elif isinstance(verified_model, InformationRules):
            return InformationToDMS(client=self.client).transform(verified_model)
        else:
            raise NeatValueError(f"Cannot merge. {name} data model is not a DMS or Information data model")
