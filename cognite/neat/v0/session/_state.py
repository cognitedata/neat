from pathlib import Path
from typing import Literal, cast

from rdflib import URIRef

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._data_model.importers import BaseImporter, InferenceImporter
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.v0.core._data_model.models.conceptual._validation import ConceptualValidation
from cognite.neat.v0.core._data_model.transformers import (
    VerifiedDataModelTransformer,
)
from cognite.neat.v0.core._instances.extractors import KnowledgeGraphExtractor
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.warnings._models import ConversionToPhysicalModelImpossibleWarning
from cognite.neat.v0.core._store import NeatDataModelStore, NeatInstanceStore
from cognite.neat.v0.core._utils.upload import UploadResultList

from .exceptions import NeatSessionError, _session_method_wrapper


class SessionState:
    def __init__(
        self,
        store_type: Literal["memory", "oxigraph"],
        storage_path: Path | None = None,
        client: NeatClient | None = None,
    ) -> None:
        self.instances = InstancesState(store_type, storage_path=storage_path)
        self.data_model_store = NeatDataModelStore()
        self.last_reference: PhysicalDataModel | ConceptualDataModel | None = None
        self.client = client
        self.quoted_source_identifiers = False

    def data_model_transform(self, *transformer: VerifiedDataModelTransformer) -> IssueList:
        if not transformer:
            raise NeatSessionError("No transformers provided.")
        start = self.data_model_store.provenance[-1].target_entity.display_name
        issues = self.data_model_store.transform(*transformer)
        last_entity = self.data_model_store.provenance[-1].target_entity
        issues.action = f"{start} &#8594; {last_entity.display_name}"
        issues.hint = "Use the .inspect.issues() for more details."
        return issues

    def data_model_import(self, importer: BaseImporter, enable_manual_edit: bool = False) -> IssueList:
        issues = self.data_model_store.import_data_model(
            importer,
            client=self.client,
            enable_manual_edit=enable_manual_edit,
        )
        if self.data_model_store.empty:
            result = "failed"
        else:
            result = self.data_model_store.provenance[-1].target_entity.display_name
        if isinstance(importer, InferenceImporter):
            issues.action = f"Inferred {result}"
        else:
            issues.action = f"Read {result}"
        if issues:
            issues.hint = "Use the .inspect.issues() for more details."
        return issues

    def write_graph(self, extractor: KnowledgeGraphExtractor) -> IssueList:
        extract_issues = self.instances.store.write(extractor)
        issues = self.data_model_store.import_graph(extractor)
        issues.extend(extract_issues)
        return issues

    def _raise_exception_if_condition_not_met(
        self,
        activity: str,
        empty_data_model_store_required: bool = False,
        empty_instances_store_required: bool = False,
        instances_required: bool = False,
        client_required: bool = False,
        has_conceptual_data_model: bool | None = None,
        can_convert_to_physical_data_model: bool = False,
        has_physical_data_model: bool | None = None,
    ) -> None:
        """Set conditions for raising an error in the session that are used by various methods in the session."""
        condition = set()
        suggestion = set()
        try_again = True
        if client_required and not self.client:
            condition.add(f"{activity} expects a client in NEAT session")
            suggestion.add("Please provide a client")
        if has_conceptual_data_model is True and self.data_model_store.try_get_last_conceptual_data_model is None:
            condition.add(f"{activity} expects conceptual data model in NEAT session")
            suggestion.add("Read in conceptual data model to neat session")
        if (
            can_convert_to_physical_data_model is True
            and (conceptual_model := self.data_model_store.try_get_last_conceptual_data_model)
            and ConceptualValidation(conceptual_model)
            .validate()
            .has_warning_type(ConversionToPhysicalModelImpossibleWarning)
        ):
            condition.add(f"{activity} expects conceptual data model that can be converted to physical data model")
            suggestion.add(
                "Read in conceptual data model and ensure that warnings that prevent conversion are resolved"
            )
        if has_physical_data_model is False and self.data_model_store.try_get_last_physical_data_model is not None:
            condition.add(f"{activity} expects no physical data model in NEAT session")
            suggestion.add("You already have a physical data model in the session")
            try_again = False
        if empty_data_model_store_required and not self.data_model_store.empty:
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
        self.store: NeatInstanceStore = _session_method_wrapper(self._create_store, "NeatSession")()

        if self.storage_path:
            print("Remember to close neat session .close() once you are done to avoid oxigraph lock.")

    def _create_store(self) -> NeatInstanceStore:
        if self.store_type == "oxigraph":
            if self.storage_path:
                self.storage_path.mkdir(parents=True, exist_ok=True)
            return NeatInstanceStore.from_oxi_local_store(storage_dir=self.storage_path)
        else:
            return NeatInstanceStore.from_memory_store()

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
