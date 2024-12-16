from cognite.neat._issues import IssueList
from cognite.neat._rules.transformers import RulesTransformer

from ._provenance import Provenance


class NeatRulesStore:
    def __init__(self):
        self._provenance = Provenance()

    def write(self, transformation: RulesTransformer) -> IssueList:
        raise NotImplementedError()
