import hashlib
from collections import defaultdict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, cast

import rdflib
from rdflib import URIRef

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model._shared import T_VerifiedDataModel, VerifiedDataModel
from cognite.neat.v0.core._data_model.exporters import BaseExporter
from cognite.neat.v0.core._data_model.exporters._base import CDFExporter, T_Export
from cognite.neat.v0.core._data_model.importers import BaseImporter
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.v0.core._data_model.transformers import (
    PhysicalToConceptual,
    VerifiedDataModelTransformer,
    VerifyAnyDataModel,
)
from cognite.neat.v0.core._instances.extractors import (
    DMSGraphExtractor,
    KnowledgeGraphExtractor,
)
from cognite.neat.v0.core._issues import IssueList, catch_issues
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._utils.upload import UploadResultList

from ._provenance import (
    EXTERNAL_AGENT,
    UNKNOWN_AGENT,
    Activity,
    Change,
    Entity,
    Provenance,
)
from .exceptions import EmptyStore, InvalidActivityInput


@dataclass(frozen=True)
class DataModelEntity(Entity):
    conceptual: ConceptualDataModel
    physical: PhysicalDataModel | None = None

    @property
    def has_physical(self) -> bool:
        return self.physical is not None

    @property
    def display_name(self) -> str:
        if self.physical is not None:
            return self.physical.display_name
        return self.conceptual.display_name


@dataclass(frozen=True)
class OutcomeEntity(Entity):
    result: UploadResultList | Path | str | URIRef


class NeatDataModelStore:
    def __init__(self) -> None:
        self.provenance = Provenance[DataModelEntity]()
        self.exports_by_source_entity_id: dict[rdflib.URIRef, list[Change[OutcomeEntity]]] = defaultdict(list)
        self._last_outcome: UploadResultList | None = None
        self._iteration_by_id: dict[Hashable, int] = {}
        self._last_issues: IssueList | None = None

    def calculate_provenance_hash(self, shorten: bool = True) -> str:
        sha256_hash = hashlib.sha256()
        for change in self.provenance:
            for id_ in [change.agent.id_, change.activity.id_, change.target_entity.id_, change.source_entity.id_]:
                sha256_hash.update(str(id_).encode("utf-8"))
        calculated_hash = sha256_hash.hexdigest()
        if shorten:
            return calculated_hash[:8]
        return calculated_hash

    def _data_model_import_verify_convert(
        self,
        importer: BaseImporter,
        validate: bool,
        client: NeatClient | None = None,
    ) -> tuple[ConceptualDataModel, PhysicalDataModel | None]:
        """Action that imports data model, verifies them and optionally converts them."""
        imported_data_model = importer.to_data_model()
        verified = VerifyAnyDataModel(validate, client).transform(imported_data_model)  # type: ignore[arg-type]
        if isinstance(verified, ConceptualDataModel):
            return verified, None
        elif isinstance(verified, PhysicalDataModel):
            return PhysicalToConceptual().transform(verified), verified
        else:
            # Bug in the code
            raise ValueError(f"Invalid output from importer: {type(verified)}")

    def _graph_import_verify_convert(
        self,
        extractor: KnowledgeGraphExtractor,
    ) -> tuple[ConceptualDataModel, PhysicalDataModel | None]:
        conceptual = extractor.get_conceptual_data_model()
        physical: PhysicalDataModel | None = None
        if isinstance(extractor, DMSGraphExtractor):
            physical = extractor.get_physical_data_model()
        return conceptual, physical

    def _manual_transform(
        self, importer: BaseImporter, validate: bool = True, client: NeatClient | None = None
    ) -> IssueList:
        result, issue_list, start, end = self._do_activity(
            partial(self._data_model_import_verify_convert, importer, validate, client)
        )

        if not result:
            return issue_list

        conceptual, physical = result
        last_change = self.provenance[-1]

        outside_agent = EXTERNAL_AGENT
        outside_activity = Activity(
            was_associated_with=outside_agent,
            started_at_time=last_change.activity.ended_at_time,
            ended_at_time=end,
            used=last_change.target_entity,
        )

        # Case 1: Source of imported data model is not known
        if not (source_id := self._get_source_id(result)):
            raise NeatValueError(
                "The source of the imported data model is unknown."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # Case 2: Source of imported data model not in data_model_store
        if not (source_entity := self.provenance.target_entity(source_id)) or not isinstance(
            source_entity, DataModelEntity
        ):
            raise NeatValueError(
                "The source of the imported data model is not in the provenance."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # Case 3: Source is not the latest source entity in the provenance change
        if source_entity.id_ != last_change.target_entity.id_:
            raise NeatValueError(
                "Imported data model is detached from the provenance chain."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # Case 4: Provenance is already at the physical state of the data model, going back to logical not possible
        if not physical and source_entity.physical:
            raise NeatValueError(
                "Data model is already in physical state, import of conceptual model not possible."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # modification took place on conceptual data model
        if not physical and not source_entity.physical:
            outside_target_entity = DataModelEntity(
                was_attributed_to=outside_agent,
                was_generated_by=outside_activity,
                conceptual=conceptual,
                physical=physical,
                issues=issue_list,
                id_=self._create_id(conceptual, physical),
            )

        # modification took place on physical data model, keep latest conceptual data model
        elif physical and source_entity.physical:
            outside_target_entity = DataModelEntity(
                was_attributed_to=outside_agent,
                was_generated_by=outside_activity,
                conceptual=last_change.target_entity.conceptual,
                physical=physical,
                issues=issue_list,
                id_=self._create_id(conceptual, physical),
            )

        else:
            raise NeatValueError("Invalid state of data model for manual transformation")

        outside_change = Change(
            source_entity=last_change.target_entity,
            agent=outside_agent,
            activity=outside_activity,
            target_entity=outside_target_entity,
            description="Manual transformation of data model outside of NEAT",
        )

        self._last_issues = issue_list
        # record change that took place outside of neat
        self.provenance.append(outside_change)

        return issue_list

    def import_graph(self, extractor: KnowledgeGraphExtractor) -> IssueList:
        if not self.empty:
            raise NeatValueError(f"Data model already exists. Cannot import {extractor.source_uri}.")
        else:
            return self.do_activity(partial(self._graph_import_verify_convert, extractor), extractor)

    def import_data_model(
        self,
        importer: BaseImporter,
        validate: bool = True,
        client: NeatClient | None = None,
        enable_manual_edit: bool = False,
    ) -> IssueList:
        if self.empty:
            return self.do_activity(
                partial(self._data_model_import_verify_convert, importer, validate, client),
                importer,
            )
        elif enable_manual_edit:
            return self._manual_transform(importer, validate, client)
        else:
            raise NeatValueError("Re-importing data model in the data model store is not allowed.")

    def transform(self, *transformer: VerifiedDataModelTransformer) -> IssueList:
        if not self.provenance:
            raise EmptyStore()

        all_issues = IssueList()
        for agent_tool in transformer:

            def action(
                transformer_item: VerifiedDataModelTransformer = agent_tool,
            ) -> tuple[ConceptualDataModel, PhysicalDataModel | None]:
                last_change = self.provenance[-1]
                source_entity = last_change.target_entity
                transformer_input = self._get_transformer_input(source_entity, transformer_item)
                transformer_output = transformer_item.transform(transformer_input)
                if isinstance(transformer_output, ConceptualDataModel):
                    return transformer_output, None
                return last_change.target_entity.conceptual, transformer_output

            issues = self.do_activity(action, agent_tool)
            all_issues.extend(issues)

        return all_issues

    def export(self, exporter: BaseExporter[T_VerifiedDataModel, T_Export]) -> T_Export:
        return self._export_activity(exporter.export, exporter, DEFAULT_NAMESPACE["export-result"])

    def export_to_file(self, exporter: BaseExporter, path: Path) -> None:
        def export_action(input_: VerifiedDataModel) -> Path:
            exporter.export_to_file(input_, path)
            return path

        self._export_activity(export_action, exporter, DEFAULT_NAMESPACE[path.name])

    def export_to_cdf(self, exporter: CDFExporter, client: NeatClient, dry_run: bool) -> UploadResultList:
        return self._export_activity(
            exporter.export_to_cdf, exporter, DEFAULT_NAMESPACE["upload-result"], client, dry_run
        )

    def do_activity(
        self,
        action: Callable[[], tuple[ConceptualDataModel, PhysicalDataModel | None]],
        agent_tool: (BaseImporter | VerifiedDataModelTransformer | KnowledgeGraphExtractor),
    ) -> IssueList:
        result, issue_list, start, end = self._do_activity(action)
        self._last_issues = issue_list

        if result:
            self._update_provenance(agent_tool, result, issue_list, start, end)
        return issue_list

    def _update_provenance(
        self,
        agent_tool: (BaseImporter | VerifiedDataModelTransformer | KnowledgeGraphExtractor),
        result: tuple[ConceptualDataModel, PhysicalDataModel | None],
        issue_list: IssueList,
        activity_start: datetime,
        activity_end: datetime,
    ) -> None:
        # set source entity
        if isinstance(agent_tool, BaseImporter | KnowledgeGraphExtractor):
            source_entity = Entity.create_with_defaults(
                was_attributed_to=UNKNOWN_AGENT,
                id_=agent_tool.source_uri,
            )
        else:
            source_entity = self.provenance[-1].target_entity

        # setting the rest of provenance components
        conceptual, physical = result
        agent = agent_tool.agent
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=activity_end,
            started_at_time=activity_start,
            used=source_entity,
        )

        target_entity = DataModelEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            conceptual=conceptual,
            physical=physical,
            issues=issue_list,
            # here id can be bumped in case id already exists
            id_=self._create_id(conceptual, physical),
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=agent_tool.description,
            source_entity=source_entity,
        )

        self.provenance.append(change)

    def _do_activity(
        self,
        action: Callable[[], tuple[ConceptualDataModel, PhysicalDataModel | None]],
    ) -> tuple[
        tuple[ConceptualDataModel, PhysicalDataModel | None],
        IssueList,
        datetime,
        datetime,
    ]:
        """This private method is used to execute an activity and return the result and issues."""
        start = datetime.now(timezone.utc)
        result: tuple[ConceptualDataModel, PhysicalDataModel | None] | None = None
        with catch_issues() as issue_list:
            result = action()
        end = datetime.now(timezone.utc)
        return result, issue_list, start, end

    def _export_activity(self, action: Callable, exporter: BaseExporter, target_id: URIRef, *exporter_args: Any) -> Any:
        if self.empty:
            raise EmptyStore()
        last_change = self.provenance[-1]
        source_entity = last_change.target_entity
        expected_types = exporter.source_types()

        if source_entity.physical is not None and isinstance(source_entity.physical, expected_types):
            input_ = cast(VerifiedDataModel, source_entity.physical).model_copy(deep=True)
        elif isinstance(source_entity.conceptual, expected_types):
            input_ = cast(VerifiedDataModel, source_entity.conceptual).model_copy(deep=True)
        else:
            available: list[type] = [ConceptualDataModel]
            if source_entity.physical is not None:
                available.append(PhysicalDataModel)
            raise InvalidActivityInput(expected=expected_types, have=tuple(available))

        # need to write source prior the export
        input_.metadata.source_id = source_entity.id_

        agent = exporter.agent
        start = datetime.now(timezone.utc)
        result: UploadResultList | Path | URIRef | None = None
        with catch_issues() as issue_list:
            # Validate the type of the result
            result = action(input_, *exporter_args)

        end = datetime.now(timezone.utc)
        self._last_issues = issue_list
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        if isinstance(result, UploadResultList | Path | URIRef):
            outcome_result: UploadResultList | Path | URIRef | str = result
        else:
            outcome_result = type(result).__name__

        target_entity = OutcomeEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=outcome_result,
            issues=issue_list,
            id_=target_id,
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=exporter.description,
            source_entity=source_entity,
        )

        self.exports_by_source_entity_id[source_entity.id_].append(change)
        if isinstance(result, UploadResultList):
            self._last_outcome = result
        return result

    @staticmethod
    def _get_transformer_input(
        source_entity: DataModelEntity, transformer: VerifiedDataModelTransformer
    ) -> ConceptualDataModel | PhysicalDataModel:
        # Case 1: We only have conceptual data model
        if source_entity.physical is None:
            if transformer.is_valid_input(source_entity.conceptual):
                return source_entity.conceptual
            raise InvalidActivityInput(expected=(PhysicalDataModel,), have=(ConceptualDataModel,))
        # Case 2: We have both data model levels and the transformer is compatible with physical data model
        elif isinstance(source_entity.physical, PhysicalDataModel) and transformer.is_valid_input(
            source_entity.physical
        ):
            return source_entity.physical
        # Case 3: We have both data model levels and the transformer is compatible with conceptual data model
        raise InvalidActivityInput(expected=(ConceptualDataModel,), have=(PhysicalDataModel,))

    def _get_source_id(self, result: tuple[ConceptualDataModel, PhysicalDataModel | None]) -> rdflib.URIRef | None:
        """Return the source of the result.

        !!! note
            This method prioritizes the source_id of the physical data model
        """
        conceptual, physical = result
        return physical.metadata.source_id if physical else conceptual.metadata.source_id

    def _create_id(self, conceptual: ConceptualDataModel, physical: PhysicalDataModel | None) -> rdflib.URIRef:
        if physical is None:
            identifier = conceptual.metadata.identifier
        else:
            identifier = physical.metadata.identifier

        # Here we check if the identifier is already in the iteration dictionary
        # to track specific changes to the same entity, if it is we increment the iteration
        if identifier not in self._iteration_by_id:
            self._iteration_by_id[identifier] = 1
            return identifier

        # If the identifier is already in the iteration dictionary we increment the iteration
        # and update identifier to include the iteration number
        self._iteration_by_id[identifier] += 1
        return identifier + f"/Iteration_{self._iteration_by_id[identifier]}"

    @property
    def try_get_last_physical_data_model(self) -> PhysicalDataModel | None:
        if not self.provenance:
            return None
        if self.provenance[-1].target_entity.physical is None:
            return None
        return self.provenance[-1].target_entity.physical

    @property
    def try_get_last_conceptual_data_model(self) -> ConceptualDataModel | None:
        if not self.provenance:
            return None
        return self.provenance[-1].target_entity.conceptual

    @property
    def last_verified_physical_data_model(self) -> PhysicalDataModel:
        if not self.provenance:
            raise EmptyStore()
        if self.provenance[-1].target_entity.physical is None:
            raise NeatValueError("No verified physical data model found in the provenance.")
        return self.provenance[-1].target_entity.physical

    @property
    def last_verified_conceptual_data_model(self) -> ConceptualDataModel:
        if not self.provenance:
            raise EmptyStore()
        return self.provenance[-1].target_entity.conceptual

    @property
    def last_verified_data_model(self) -> ConceptualDataModel | PhysicalDataModel | None:
        if not self.provenance:
            return None
        last_entity = self.provenance[-1].target_entity
        return last_entity.physical or last_entity.conceptual

    @property
    def last_issues(self) -> IssueList | None:
        return self._last_issues

    @property
    def last_outcome(self) -> UploadResultList:
        if self._last_outcome is not None:
            return self._last_outcome
        raise NeatValueError("No outcome found in the provenance.")

    @property
    def empty(self) -> bool:
        """Check if the store is empty."""
        return not self.provenance
