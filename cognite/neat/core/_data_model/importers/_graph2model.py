from cognite.neat.core._data_model._shared import ReadRules
from cognite.neat.core._data_model.models import InformationInputRules
from cognite.neat.core._store import NeatGraphStore

from ._base import BaseImporter


class GraphImporter(BaseImporter[InformationInputRules]):
    """Infers a data model from the data in a Graph."""

    def __init__(self, store: NeatGraphStore) -> None:
        self.store = store

    def to_rules(self) -> ReadRules[InformationInputRules]:
        raise NotImplementedError()
