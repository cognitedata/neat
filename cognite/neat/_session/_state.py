from pathlib import Path
from typing import Literal, cast

from rdflib import URIRef

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
        issues.extend(extract_issues)
        return issues

    def _raise_exception_if_condition_not_met(
        self,
        activity: str,
        empty_rules_store_required: bool = False,
        empty_instances_store_required: bool = False,
        instances_required: bool = False,
        client_required: bool = False,
        has_information_rules: bool | None = None,
        has_dms_rules: bool | None = None,
    ) -> None:
        """Set conditions for raising an error in the session that are used by various methods in the session."""
        condition = set()
        suggestion = set()
        try_again = True
        if client_required and not self.client:
            condition.add(f"{activity} expects a client in NEAT session")
            suggestion.add("Please provide a client")
        if has_information_rules is True and self.rule_store.try_get_last_information_rules is None:
            condition.add(f"{activity} expects information rules in NEAT session")
            suggestion.add("Read in information rules to neat session")
        if has_dms_rules is False and self.rule_store.try_get_last_dms_rules is not None:
            condition.add(f"{activity} expects no DMS data model in NEAT session")
            suggestion.add("You already have a DMS data model in the session")
            try_again = False
        if empty_rules_store_required and not self.rule_store.empty:
            condition.add(f"{activity} expects no data model in NEAT session")
            suggestion.add("Start new session")
        if empty_instances_store_required and not self.instances.empty:
            condition.add(f"{activity} expects no instances in NEAT session")
            suggestion.add("Start new session")
        if instances_required and self.instances.empty:
            condition.add(f"{activity} expects instances in NEAT session")
            suggestion.add("Read in instances to neat session")

        if condition:
            message = ". ".join(condition) + ". " + ". ".join(suggestion) + "."
            if try_again:
                message += " And try again."
            raise NeatSessionError(message)


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
        # These contain prefixes added by Neat at the extraction stage.
        # We store them such that they can be removed in the load stage.
        self.neat_prefix_by_predicate_uri: dict[URIRef, str] = {}
        self.neat_prefix_by_type_uri: dict[URIRef, str] = {}

        # Ensure that error handling is done in the constructor
        self.store: NeatGraphStore = _session_method_wrapper(self._create_store, "NeatSession")()

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
