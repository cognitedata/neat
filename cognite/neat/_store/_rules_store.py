from cognite.neat._issues import IssueList
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer

from ._provenance import Provenance


class NeatRulesStore:
    def __init__(self):
        self._provenance = Provenance()

    def write(self, importer: BaseImporter) -> IssueList:
        raise NotImplementedError()

    def transform(self, transformer: RulesTransformer) -> IssueList:
        raise NotImplementedError()

    def read(self, exporter: BaseExporter) -> IssueList:
        raise NotImplementedError()
