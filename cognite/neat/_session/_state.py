from pathlib import Path
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

from .exceptions import NeatSessionError, _session_method_wrapper


class SessionState:
    def __init__(
        self,
        store_type: Literal["memory", "oxigraph"],
        storage_path: Path | None = None,
        client: NeatClient | None = None,
    ) -> None:
        self.instances = InstancesState(store_type, storage_path=storage_path)
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

    def rule_import(self, importer: BaseImporter, enable_manual_edit: bool = False) -> IssueList:
        issues = self.rule_store.import_rules(
            importer,
            client=self.client,
            enable_manual_edit=enable_manual_edit,
        )
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


class InstancesState:
    def __init__(
        self,
        store_type: Literal["memory", "oxigraph"],
        storage_path: Path | None = None,
    ) -> None:
        self.store_type = store_type
        self.storage_path = storage_path
        self.issue_lists = IssueList()
        self.outcome = UploadResultList()

        # Ensure that error handling is done in the constructor
        self.store = _session_method_wrapper(self._create_store, "NeatSession")()

        if self.storage_path:
            print("Remember to close neat session .close() once you are done to avoid oxigraph lock.")

    def _create_store(self) -> NeatGraphStore:
        if self.store_type == "oxigraph":
            if self.storage_path:
                self.storage_path.mkdir(parents=True, exist_ok=True)
            return NeatGraphStore.from_oxi_local_store(storage_dir=self.storage_path)
        else:
            return NeatGraphStore.from_memory_store()

    @property
    def empty(self) -> bool:
        return self.store.empty

    @property
    def last_outcome(self) -> UploadResultList:
        if not self.outcome:
            raise NeatSessionError(
                "No outcome available. Try using [bold].to.cdf.instances[/bold] to upload a data instance."
            )
        return cast(UploadResultList, self.outcome[-1])
