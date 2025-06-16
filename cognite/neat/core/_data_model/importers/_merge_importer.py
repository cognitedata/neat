from cognite.neat.core._client import NeatClient
from cognite.neat.core._data_model._shared import ImportedDataModel
from cognite.neat.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
    UnverifiedConceptualDataModel,
    UnverifiedPhysicalDataModel,
)
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

    def to_data_model(self) -> ImportedDataModel[UnverifiedPhysicalDataModel]:
        # Local import to avoid circular import
        from cognite.neat.core._data_model.transformers import MergePhysicalDataModel

        existing_input = self.existing.to_data_model()
        existing_dms = self._get_dms_model(existing_input.unverified_data_model, "Existing")
        additional_input = self.additional.to_data_model()
        additional_dms = self._get_dms_model(additional_input.unverified_data_model, "Additional")
        if additional_dms.metadata.identifier != existing_dms.metadata.identifier:
            raise NeatValueError("Cannot merge. The identifiers of the two data models do not match.")
        merged = MergePhysicalDataModel(additional_dms).transform(existing_dms)

        return ImportedDataModel(
            unverified_data_model=UnverifiedPhysicalDataModel.load(merged.dump()),
            context=additional_input.context or existing_input.context,
        )

    def _get_dms_model(
        self, input_model: UnverifiedConceptualDataModel | UnverifiedPhysicalDataModel | None, name: str
    ) -> PhysicalDataModel:
        # Local import to avoid circular import
        from cognite.neat.core._data_model.transformers import ConceptualToPhysical

        if input_model is None:
            raise NeatValueError(f"Cannot merge. {name} data model failed read.")

        verified_model = input_model.as_verified_data_model()
        if isinstance(verified_model, PhysicalDataModel):
            return verified_model
        elif isinstance(verified_model, ConceptualDataModel):
            return ConceptualToPhysical(client=self.client).transform(verified_model)
        else:
            raise NeatValueError(f"Cannot merge. {name} data model is not a DMS or Information data model")
