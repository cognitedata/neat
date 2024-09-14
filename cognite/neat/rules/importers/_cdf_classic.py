from cognite.neat.rules._shared import ReadRules
from cognite.neat.rules.models import DMSInputRules
from cognite.neat.store import NeatGraphStore

from ._base import BaseImporter


class ClassicImporter(BaseImporter[DMSInputRules]):
    def __init__(self, store: NeatGraphStore) -> None:
        raise NotImplementedError()

    def to_rules(self) -> ReadRules[DMSInputRules]:
        raise NotImplementedError()
