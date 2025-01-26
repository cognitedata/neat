from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat._client import NeatClient
from cognite.neat._graph.extractors import KnowledgeGraphExtractor
from cognite.neat._issues import IssueList
from cognite.neat._rules.importers import BaseImporter, InferenceImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.transformers import (
    VerifiedRulesTransformer,
)
from cognite.neat._store import NeatGraphStore, NeatRulesStore
from cognite.neat._utils.upload import UploadResultList

from .exceptions import NeatSessionError


class SessionState:
    def __init__(self, store_type: Literal["memory", "oxigraph"], client: NeatClient | None = None) -> None:
        self.instances = InstancesState(store_type)
        self.rule_store = NeatRulesStore()
        self.last_reference: DMSRules | InformationRules | None = None
        self.client = client
        self.quoted_source_identifiers = False

    def rule_transform(self, *transformer: VerifiedRulesTransformer) -> IssueList:
        if not transformer:
            raise NeatSessionError("No transformers provided.")

        start = self.rule_store.provenance[-1].target_entity.display_name
        issues = self.rule_store.transform(*transformer)
        last_entity = self.rule_store.provenance[-1].target_entity
        issues.action = f"{start} &#8594; {last_entity.display_name}"
        issues.hint = "Use the .inspect.issues() for more details."
        self.instances.store.add_rules(last_entity.information)
        return issues

    def rule_import(self, importer: BaseImporter) -> IssueList:
        issues = self.rule_store.import_rules(importer, client=self.client)
        if self.rule_store.empty:
            result = "failed"
        else:
            result = self.rule_store.provenance[-1].target_entity.display_name
        if isinstance(importer, InferenceImporter):
            issues.action = f"Inferred {result}"
        else:
            issues.action = f"Read {result}"
        if issues:
            issues.hint = "Use the .inspect.issues() for more details."
        return issues

    def write_graph(self, extractor: KnowledgeGraphExtractor) -> IssueList:
        extract_issues = self.instances.store.write(extractor)
        issues = self.rule_store.import_graph(extractor)
        self.instances.store.add_rules(self.rule_store.last_verified_information_rules)
        issues.extend(extract_issues)
        return issues


@dataclass
class InstancesState:
    store_type: Literal["memory", "oxigraph"]
    issue_lists: list[IssueList] = field(default_factory=list)
    outcome: list[UploadResultList] = field(default_factory=list)
    _store: NeatGraphStore | None = field(init=False, default=None)

    @property
    def store(self) -> NeatGraphStore:
        if not self.has_store:
            if self.store_type == "oxigraph":
                self._store = NeatGraphStore.from_oxi_local_store()
            else:
                self._store = NeatGraphStore.from_memory_store()
        return cast(NeatGraphStore, self._store)

    @property
    def has_store(self) -> bool:
        return self._store is not None

    @property
    def last_outcome(self) -> UploadResultList:
        if not self.outcome:
            raise NeatSessionError(
                "No outcome available. Try using [bold].to.cdf.instances[/bold] to upload a data minstances."
            )
        return self.outcome[-1]
