from pathlib import Path
from typing import TypeAlias

from cognite.neat._client import NeatClient
from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.loaders import BaseLoader
from cognite.neat._graph.transformers import BaseTransformer, BaseTransformerStandardised
from cognite.neat._issues import IssueList
from cognite.neat._rules.exporters import BaseExporter, CDFExporter
from cognite.neat._rules.exporters._base import T_Export, T_VerifiedRules
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer
from cognite.neat._utils.upload import UploadResultList

Action: TypeAlias = BaseImporter | BaseExtractor | RulesTransformer | BaseTransformerStandardised | BaseTransformer


class NeatState:
    """The neat state contains three main components:

    - Instances: stored in a triple store.
    - Conceptual rules: The schema for conceptual rules.
    - Physical rules: The schema for physical rules.
    """

    @property
    def status(self) -> str:
        raise NotImplementedError()

    def change(self, action: Action) -> IssueList:
        raise NotImplementedError

    def export(self, exporter: BaseExporter[T_VerifiedRules, T_Export]) -> T_Export:  # type: ignore[type-arg, type-var]
        raise NotImplementedError

    def export_to_file(self, exporter: BaseExporter, path: Path) -> None:
        raise NotImplementedError

    def export_to_cdf(self, exporter: CDFExporter, client: NeatClient, dry_run: bool) -> UploadResultList:
        raise NotImplementedError

    def load(self, loader: BaseLoader) -> UploadResultList:
        raise NotImplementedError
