from typing import cast

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer

from ._provenance import ModelEntity, Provenance


class NeatRulesStore:
    def __init__(self):
        self._provenance = Provenance()

    def write(self, importer: BaseImporter) -> IssueList:
        raise NotImplementedError()

    def transform(self, transformer: RulesTransformer) -> IssueList:
        raise NotImplementedError()

    def read(self, exporter: BaseExporter) -> IssueList:
        raise NotImplementedError()

    def get_last_entity(self) -> ModelEntity:
        if not self._provenance:
            raise NeatValueError("No entity found in the provenance.")
        return cast(ModelEntity, self._provenance[-1].target_entity)
