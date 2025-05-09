from cognite.neat.core._rules._shared import InputRules, ReadRules
from cognite.neat.core._rules.models import DMSInputRules

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
        raise NotImplementedError()
