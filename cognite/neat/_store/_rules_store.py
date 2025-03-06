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

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors import DMSGraphExtractor, KnowledgeGraphExtractor
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import T_VerifiedRules, VerifiedRules
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.exporters._base import CDFExporter, T_Export
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.transformers import DMSToInformation, VerifiedRulesTransformer, VerifyAnyRules
from cognite.neat._utils.upload import UploadResultList

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

    def _rules_import_verify_convert(
        self,
        importer: BaseImporter,
        validate: bool,
        client: NeatClient | None = None,
    ) -> tuple[InformationRules, DMSRules | None]:
        """Action that imports rules, verifies them and optionally converts them."""
        read_rules = importer.to_rules()
        verified = VerifyAnyRules(validate, client).transform(read_rules)  # type: ignore[arg-type]
        if isinstance(verified, InformationRules):
            return verified, None
        elif isinstance(verified, DMSRules):
            return DMSToInformation().transform(verified), verified
        else:
            # Bug in the code
            raise ValueError(f"Invalid output from importer: {type(verified)}")

    def _graph_import_verify_convert(
        self,
        extractor: KnowledgeGraphExtractor,
    ) -> tuple[InformationRules, DMSRules | None]:
        info = extractor.get_information_rules()
        dms: DMSRules | None = None
        if isinstance(extractor, DMSGraphExtractor):
            dms = extractor.get_dms_rules()
        return info, dms

    def _manual_transform(
        self, importer: BaseImporter, validate: bool = True, client: NeatClient | None = None
    ) -> IssueList:
        result, issue_list, start, end = self._do_activity(
            partial(self._rules_import_verify_convert, importer, validate, client)
        )

        if not result:
            return issue_list

        info, dms = result
        last_change = self.provenance[-1]

        outside_agent = EXTERNAL_AGENT
        outside_activity = Activity(
            was_associated_with=outside_agent,
            started_at_time=last_change.activity.ended_at_time,
            ended_at_time=end,
            used=last_change.target_entity,
        )

        # Case 1: Source of imported rules is not known
        if not (source_id := self._get_source_id(result)):
            raise NeatValueError(
                "The source of the imported rules is unknown."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # Case 2: Source of imported rules not in rules_store
        if not (source_entity := self.provenance.target_entity(source_id)) or not isinstance(
            source_entity, RulesEntity
        ):
            raise NeatValueError(
                "The source of the imported rules is not in the provenance."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # Case 3: Source is not the latest source entity in the provenance change
        if source_entity.id_ != last_change.target_entity.id_:
            raise NeatValueError(
                "Imported rules are detached from the provenance chain."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # Case 4: Provenance is already at the physical state of the data model, going back to logical not possible
        if not dms and source_entity.dms:
            raise NeatValueError(
                "Rules are already in physical state, import of logical model not possible."
                " Import will be skipped. Start a new NEAT session and import the data model there."
            )

        # modification took place on information rules
        if not dms and not source_entity.dms:
            outside_target_entity = RulesEntity(
                was_attributed_to=outside_agent,
                was_generated_by=outside_activity,
                information=info,
                dms=dms,
                issues=issue_list,
                id_=self._create_id(info, dms),
            )

        # modification took place on dms rules, keep latest information rules
        elif dms and source_entity.dms:
            outside_target_entity = RulesEntity(
                was_attributed_to=outside_agent,
                was_generated_by=outside_activity,
                information=last_change.target_entity.information,
                dms=dms,
                issues=issue_list,
                id_=self._create_id(info, dms),
            )

        else:
            raise NeatValueError("Invalid state of rules for manual transformation")

        outside_change = Change(
            source_entity=last_change.target_entity,
            agent=outside_agent,
            activity=outside_activity,
            target_entity=outside_target_entity,
            description="Manual transformation of rules outside of NEAT",
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

    def import_rules(
        self,
        importer: BaseImporter,
        validate: bool = True,
        client: NeatClient | None = None,
        enable_manual_edit: bool = False,
    ) -> IssueList:
        if self.empty:
            return self.do_activity(
                partial(self._rules_import_verify_convert, importer, validate, client),
                importer,
            )
        elif enable_manual_edit:
            return self._manual_transform(importer, validate, client)
        else:
            raise NeatValueError("Re-importing rules in the rules store is not allowed.")

    def transform(self, *transformer: VerifiedRulesTransformer) -> IssueList:
        if not self.provenance:
            raise EmptyStore()

        all_issues = IssueList()
        for agent_tool in transformer:

            def action(
                transformer_item=agent_tool,
            ) -> tuple[InformationRules, DMSRules | None]:
                last_change = self.provenance[-1]
                source_entity = last_change.target_entity
                transformer_input = self._get_transformer_input(source_entity, transformer_item)
                transformer_output = transformer_item.transform(transformer_input)
                if isinstance(transformer_output, InformationRules):
                    return transformer_output, None
                return last_change.target_entity.information, transformer_output

            issues = self.do_activity(action, agent_tool)
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
    ):
        result, issue_list, start, end = self._do_activity(action)
        self._last_issues = issue_list

        if result:
            self._update_provenance(agent_tool, result, issue_list, start, end)
        return issue_list

    def _update_provenance(
        self,
        agent_tool: BaseImporter | VerifiedRulesTransformer | KnowledgeGraphExtractor,
        result: tuple[InformationRules, DMSRules | None],
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
        info, dms = result
        agent = agent_tool.agent
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=activity_end,
            started_at_time=activity_start,
            used=source_entity,
        )

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

    def _do_activity(
        self,
        action: Callable[[], tuple[InformationRules, DMSRules | None]],
    ):
        """This private method is used to execute an activity and return the result and issues."""
        start = datetime.now(timezone.utc)
        result: tuple[InformationRules, DMSRules | None] | None = None
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

        if source_entity.dms is not None and isinstance(source_entity.dms, expected_types):
            input_ = cast(VerifiedRules, source_entity.dms).model_copy(deep=True)
        elif isinstance(source_entity.information, expected_types):
            input_ = cast(VerifiedRules, source_entity.information).model_copy(deep=True)
        else:
            available: list[type] = [InformationRules]
            if source_entity.dms is not None:
                available.append(DMSRules)
            raise InvalidActivityInput(expected=expected_types, have=tuple(available))

        # need to write source prior the export
        input_.metadata.source_id = source_entity.id_

        agent = exporter.agent
        start = datetime.now(timezone.utc)
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

    def _get_source_id(self, result: tuple[InformationRules, DMSRules | None]) -> rdflib.URIRef | None:
        """Return the source of the result.

        !!! note
            This method prioritizes the source_id of the DMS rules
        """
        info, dms = result
        return dms.metadata.source_id if dms else info.metadata.source_id

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
    def try_get_last_dms_rules(self) -> DMSRules | None:
        if not self.provenance:
            return None
        if self.provenance[-1].target_entity.dms is None:
            return None
        return self.provenance[-1].target_entity.dms

    @property
    def try_get_last_information_rules(self) -> InformationRules | None:
        if not self.provenance:
            return None
        return self.provenance[-1].target_entity.information

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
    def last_verified_rules(self) -> InformationRules | DMSRules | None:
        if not self.provenance:
            return None
        last_entity = self.provenance[-1].target_entity
        return last_entity.dms or last_entity.information

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
