import hashlib
from collections import defaultdict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rdflib
from cognite.client import data_modeling as dm
from rdflib import URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors import DMSGraphExtractor, KnowledgeGraphExtractor
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import ReadRules, Rules, T_VerifiedRules, VerifiedRules
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.exporters._base import CDFExporter, T_Export
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.transformers import DMSToInformation, VerifiedRulesTransformer, VerifyAnyRules
from cognite.neat._utils.upload import UploadResultList

from ._provenance import UNKNOWN_AGENT, Activity, Change, Entity, Provenance
from .exceptions import EmptyStore, InvalidActivityInput


@dataclass(frozen=True)
class RulesEntity(Entity):
    information: InformationRules
    dms: DMSRules | None = None

    @property
    def has_dms(self) -> bool:
        return self.dms is not None

    @property
    def display_name(self) -> str:
        if self.dms is not None:
            return self.dms.display_name
        return self.information.display_name


@dataclass(frozen=True)
class OutcomeEntity(Entity):
    result: UploadResultList | Path | str | URIRef


class NeatRulesStore:
    def __init__(self) -> None:
        self.provenance = Provenance[RulesEntity]()
        self.exports_by_source_entity_id: dict[rdflib.URIRef, list[Change[OutcomeEntity]]] = defaultdict(list)
        self._last_outcome: UploadResultList | None = None
        self._iteration_by_id: dict[Hashable, int] = {}

    def calculate_provenance_hash(self, shorten: bool = True) -> str:
        sha256_hash = hashlib.sha256()
        for change in self.provenance:
            for id_ in [change.agent.id_, change.activity.id_, change.target_entity.id_, change.source_entity.id_]:
                sha256_hash.update(str(id_).encode("utf-8"))
        calculated_hash = sha256_hash.hexdigest()
        if shorten:
            return calculated_hash[:8]
        return calculated_hash

    def import_rules(
        self, importer: BaseImporter, validate: bool = True, client: NeatClient | None = None
    ) -> IssueList:
        def action() -> tuple[InformationRules, DMSRules | None]:
            read_rules = importer.to_rules()
            verified = VerifyAnyRules(validate, client).transform(read_rules)
            if isinstance(verified, InformationRules):
                return verified, None
            elif isinstance(verified, DMSRules):
                return DMSToInformation().transform(verified), verified
            else:
                # Bug in the code
                raise ValueError(f"Invalid output from importer: {type(verified)}")

        return self.import_action(action, importer)

    def import_graph(self, extractor: KnowledgeGraphExtractor) -> IssueList:
        def action() -> tuple[InformationRules, DMSRules | None]:
            info = extractor.get_information_rules()
            dms: DMSRules | None = None
            if isinstance(extractor, DMSGraphExtractor):
                dms = extractor.get_dms_rules()
            return info, dms

        return self.import_action(action, extractor)

    def import_action(
        self,
        action: Callable[[], tuple[InformationRules, DMSRules | None]],
        agent_tool: BaseImporter | KnowledgeGraphExtractor,
    ) -> IssueList:
        if self.provenance:
            raise NeatValueError(f"Data model already exists. Cannot import {agent_tool.source_uri}.")
        return self.do_activity(action, agent_tool)

    def transform(self, *transformer: VerifiedRulesTransformer) -> IssueList:
        if not self.provenance:
            raise EmptyStore()

        all_issues = IssueList()
        for item in transformer:

            def action(transformer_item=item) -> tuple[InformationRules, DMSRules | None]:
                last_change = self.provenance[-1]
                source_entity = last_change.target_entity
                transformer_input = self._get_transformer_input(source_entity, transformer_item)
                transformer_output = transformer_item.transform(transformer_input)
                if isinstance(transformer_output, InformationRules):
                    return transformer_output, None
                return last_change.target_entity.information, transformer_output

            issues = self.do_activity(action, item)
            all_issues.extend(issues)
        return all_issues

    def export(self, exporter: BaseExporter[T_VerifiedRules, T_Export]) -> T_Export:
        return self._export_activity(exporter.export, exporter, DEFAULT_NAMESPACE["export-result"])

    def export_to_file(self, exporter: BaseExporter, path: Path) -> None:
        def export_action(input_: VerifiedRules) -> Path:
            exporter.export_to_file(input_, path)
            return path

        self._export_activity(export_action, exporter, DEFAULT_NAMESPACE[path.name])

    def export_to_cdf(self, exporter: CDFExporter, client: NeatClient, dry_run: bool) -> UploadResultList:
        return self._export_activity(
            exporter.export_to_cdf, exporter, DEFAULT_NAMESPACE["upload-result"], client, dry_run
        )

    def do_activity(
        self,
        action: Callable[[], tuple[InformationRules, DMSRules | None]],
        agent_tool: BaseImporter | VerifiedRulesTransformer | KnowledgeGraphExtractor,
    ) -> IssueList:
        if isinstance(agent_tool, BaseImporter | KnowledgeGraphExtractor):
            source_entity = Entity.create_with_defaults(
                was_attributed_to=UNKNOWN_AGENT,
                id_=agent_tool.source_uri,
            )
        else:
            # This is a transformer
            source_entity = self.provenance[-1].target_entity

        start = datetime.now(timezone.utc)
        result: tuple[InformationRules, DMSRules | None] | None = None
        with catch_issues() as issue_list:
            result = action()

        end = datetime.now(timezone.utc)
        agent = agent_tool.agent
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        if result is None:
            return issue_list
        info, dms = result

        target_entity = RulesEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            information=info,
            dms=dms,
            issues=issue_list,
            # here id can be bumped in case id already exists
            id_=self._create_id(info, dms),
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=agent_tool.description,
            source_entity=source_entity,
        )
        self.provenance.append(change)
        return issue_list

    def _export_activity(self, action: Callable, exporter: BaseExporter, target_id: URIRef, *exporter_args: Any) -> Any:
        if self.empty:
            raise EmptyStore()
        last_change = self.provenance[-1]
        source_entity = last_change.target_entity
        expected_types = exporter.source_types()

        if source_entity.dms is not None and isinstance(source_entity.dms, expected_types):
            input_ = source_entity.dms
        elif isinstance(source_entity.information, expected_types):
            input_ = source_entity.information
        else:
            available = [InformationRules]
            if source_entity.dms is not None:
                available.append(DMSRules)
            raise InvalidActivityInput(expected=expected_types, have=tuple(available))

        agent = exporter.agent
        start = datetime.now(timezone.utc)
        with catch_issues() as issue_list:
            # Validate the type of the result
            result = action(input_, *exporter_args)

        end = datetime.now(timezone.utc)
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        if isinstance(result, UploadResultList | Path | URIRef):
            outcome_result = result
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
        source_entity: RulesEntity, transformer: VerifiedRulesTransformer
    ) -> InformationRules | DMSRules:
        # Case 1: We only have information rules
        if source_entity.dms is None:
            if transformer.is_valid_input(source_entity.information):
                return source_entity.information
            raise InvalidActivityInput(expected=(DMSRules,), have=(InformationRules,))
        # Case 2: We have both information and dms rules and the transformer is compatible with dms rules
        elif isinstance(source_entity.dms, DMSRules) and transformer.is_valid_input(source_entity.dms):
            return source_entity.dms
        # Case 3: We have both information and dms rules and the transformer is compatible with information rules
        raise InvalidActivityInput(expected=(InformationRules,), have=(DMSRules,))

    def _update_source_entity(self, source_entity: Entity, result: Rules, issue_list: IssueList) -> Entity:
        """Update source entity to keep the unbroken provenance chain of changes."""

        # Case 1: Store not empty, source of imported rules is not known
        if not (source_id := self._get_source_id(result)):
            raise NeatValueError(
                "The data model to be read to the current NEAT session"
                " has no relation to the session content."
                " Import will be skipped."
                "\n\nSuggestions:\n\t(1) Start a new NEAT session and "
                "import the data model there."
            )

        # We are taking target entity as it is the entity that produce rules
        # which were updated by activities outside of the rules tore
        update_source_entity: Entity | None = self.provenance.target_entity(source_id)

        # Case 2: source of imported rules not in rules_store
        if not update_source_entity:
            raise NeatValueError(
                "The source of the data model being imported is not in"
                " the content of this NEAT session."
                " Import will be skipped."
                "\n\nSuggestions:"
                "\n\t(1) Start a new NEAT session and import the data model source"
                "\n\t(2) Then import the data model itself"
            )

        # Case 3: source_entity in rules_store and but it is not the latest entity
        if self.provenance[-1].target_entity.id_ != update_source_entity.id_:
            raise NeatValueError(
                "Source of imported data model is not the latest entity in the data model provenance."
                "Pruning required to set the source entity to the latest entity in the provenance."
            )

        # Case 4: source_entity in rules_store and it is not the latest target entity
        if self.provenance[-1].target_entity.id_ != update_source_entity.id_:
            raise NeatValueError(
                "Source of imported rules is not the latest entity in the provenance."
                "Pruning required to set the source entity to the latest entity in the provenance."
            )

        # Case 5: source_entity in rules_store and it is the latest entity
        # Here we need to check if the source and target entities are identical
        # if they are ... we should raise an error and skip importing
        # for now we will just return the source entity that we managed to extract

        return update_source_entity or source_entity

    def _get_source_id(self, result: Rules) -> rdflib.URIRef | None:
        """Return the source of the result."""

        if isinstance(result, ReadRules) and result.rules is not None and result.rules.metadata.source_id:
            return rdflib.URIRef(result.rules.metadata.source_id)
        if isinstance(result, VerifiedRules):
            return result.metadata.source_id
        return None

    def _get_data_model_id(self, result: Rules) -> dm.DataModelId | None:
        """Return the source of the result."""

        if isinstance(result, ReadRules) and result.rules is not None:
            return result.rules.metadata.as_data_model_id()
        if isinstance(result, VerifiedRules):
            return result.metadata.as_data_model_id()
        return None

    def _create_id(self, info: InformationRules, dms: DMSRules | None) -> rdflib.URIRef:
        if dms is None:
            identifier = info.metadata.identifier
        else:
            identifier = dms.metadata.identifier

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
    def last_verified_dms_rules(self) -> DMSRules:
        if not self.provenance:
            raise EmptyStore()
        if self.provenance[-1].target_entity.dms is None:
            raise NeatValueError("No verified DMS rules found in the provenance.")
        return self.provenance[-1].target_entity.dms

    @property
    def last_verified_information_rules(self) -> InformationRules:
        if not self.provenance:
            raise EmptyStore()
        return self.provenance[-1].target_entity.information

    @property
    def last_issues(self) -> IssueList:
        if not self.provenance:
            raise EmptyStore()
        if self.provenance[-1].target_entity.issues:
            return self.provenance[-1].target_entity.issues
        return self.provenance[-1].source_entity.issues

    @property
    def last_outcome(self) -> UploadResultList:
        if self._last_outcome is not None:
            return self._last_outcome
        raise NeatValueError("No outcome found in the provenance.")

    @property
    def empty(self) -> bool:
        """Check if the store is empty."""
        return not self.provenance
