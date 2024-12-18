import hashlib
from collections.abc import Callable, Hashable
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, cast

import rdflib

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import ReadRules, T_VerifiedRules, VerifiedRules
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.exporters._base import CDFExporter, T_Export
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models._base_input import InputRules
from cognite.neat._rules.transformers import RulesTransformer
from cognite.neat._utils.upload import UploadResultList

from ._provenance import EMPTY_ENTITY, UNKNOWN_AGENT, Activity, Agent, Change, Entity, ModelEntity, Provenance


class NeatRulesStore:
    def __init__(self) -> None:
        self.provenance = Provenance()
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

    def import_(self, importer: BaseImporter) -> IssueList:
        agent = importer.agent
        source_entity = Entity(
            was_attributed_to=UNKNOWN_AGENT,
            id_=importer.source_uri,
        )
        return self._run(importer.to_rules, agent, source_entity, importer.description)[1]

    def transform(self, *transformer: RulesTransformer) -> IssueList:
        all_issues = IssueList()
        for item in transformer:
            last_entity = self.get_last_successful_entity()

            transform_issues = self._run(
                # The item and last_entity will change in the loop, however, this will
                # be ok as the run method will execute the lambda immediately
                lambda: item.transform(last_entity.result),  # noqa: B023
                item.agent,
                last_entity,
                item.description,
            )[1]
            all_issues.extend(transform_issues)
        return all_issues

    def export(self, exporter: BaseExporter[T_VerifiedRules, T_Export], path: Path | None = None) -> T_Export:
        return self._export(exporter.export, exporter.agent, exporter.description)

    def export_to_file(self, exporter: BaseExporter[T_VerifiedRules, T_Export], path: Path) -> None:
        return self._export(partial(exporter.export_to_file, filepath=path), exporter.agent, exporter.description)

    def export_to_cdf(self, exporter: CDFExporter, client: NeatClient, dry_run: bool) -> UploadResultList:
        return self._export(
            partial(exporter.export_to_cdf, client=client, dry_run=dry_run), exporter.agent, exporter.description
        )

    def _export(self, action: Callable[[Any], Any], agent: Agent, description: str) -> Any:
        last_entity: ModelEntity | None = None
        for change in reversed(self.provenance):
            if (
                isinstance(change.target_entity, ModelEntity)
                and isinstance(change.target_entity.result, DMSRules)
            ):
                last_entity = change.target_entity
                break
        if last_entity is None:
            raise NeatValueError("No verified DMS rules found in the provenance.")
        rules = last_entity.result
        result, _ = self._run(lambda: action(rules), agent, last_entity, description)
        return result

    def _run(
        self, action: Callable[[], Any], agent: Agent, source_entity: Entity, description: str
    ) -> tuple[Any, IssueList]:
        start = datetime.now(timezone.utc)
        issue_list = IssueList()
        result: Any = None
        with catch_issues(issue_list) as _:
            result = action()
        end = datetime.now(timezone.utc)
        if hasattr(result, "issues") and isinstance(result.issues, IssueList):
            issue_list.extend(result.issues)

        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        target_entity = ModelEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=result,
            id_=self._create_id(result),
        )

        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=description,
            source_entity=source_entity,
        )
        self.provenance.append(change)
        return result, issue_list

    def _create_id(self, result: Any) -> rdflib.URIRef:
        identifier: rdflib.URIRef
        if result is None:
            identifier = EMPTY_ENTITY.id_
        elif isinstance(result, ReadRules):
            if result.rules is None:
                identifier = EMPTY_ENTITY.id_
            else:
                identifier = result.rules.metadata.identifier
        elif isinstance(result, VerifiedRules):
            identifier = result.metadata.identifier
        else:
            identifier = DEFAULT_NAMESPACE["unknown-entity"]

        if identifier not in self._iteration_by_id:
            self._iteration_by_id[identifier] = 1
            return identifier
        self._iteration_by_id[identifier] += 1
        return identifier + f"/Iteration_{self._iteration_by_id[identifier]}"

    def get_last_entity(self) -> ModelEntity:
        if not self.provenance:
            raise NeatValueError("No entity found in the provenance.")
        return cast(ModelEntity, self.provenance[-1].target_entity)

    def get_last_successful_entity(self) -> ModelEntity:
        for change in reversed(self.provenance):
            if isinstance(change.target_entity, ModelEntity) and change.target_entity.result:
                return change.target_entity
        raise NeatValueError("No successful entity found in the provenance.")

    @property
    def has_unverified_rules(self) -> bool:
        return any(
            isinstance(change.target_entity, ModelEntity)
            and isinstance(change.target_entity.result, ReadRules)
            and change.target_entity.result.rules is not None
            for change in self.provenance
        )

    @property
    def has_verified_rules(self) -> bool:
        return any(
            isinstance(change.target_entity, ModelEntity)
            and isinstance(change.target_entity.result, DMSRules | InformationRules)
            for change in self.provenance
        )

    @property
    def last_unverified_rule(self) -> InputRules:
        for change in reversed(self.provenance):
            if (
                isinstance(change.target_entity, ModelEntity)
                and isinstance(change.target_entity.result, ReadRules)
                and change.target_entity.result.rules is not None
            ):
                return change.target_entity.result.rules

        raise NeatValueError("No unverified rule found in the provenance.")

    @property
    def last_verified_rule(self) -> DMSRules | InformationRules:
        for change in reversed(self.provenance):
            if (
                isinstance(change.target_entity, ModelEntity)
                and isinstance(change.target_entity.result, DMSRules | InformationRules)
            ):
                return change.target_entity.result
        raise NeatValueError("No verified rule found in the provenance.")

    @property
    def last_verified_dms_rules(self) -> DMSRules:
        for change in reversed(self.provenance):
            if (
                isinstance(change.target_entity, ModelEntity)
                and isinstance(change.target_entity.result, DMSRules)
            ):
                return change.target_entity.result
        raise NeatValueError("No verified DMS rules found in the provenance.")

    @property
    def last_issues(self) -> IssueList:
        if not self.provenance:
            raise NeatValueError("No issues found in the provenance.")
        return self.provenance[-1].target_entity.result.issues

    @property
    def last_outcome(self) -> UploadResultList:
        for change in reversed(self.provenance):
            if isinstance(change.target_entity, ModelEntity) and isinstance(
                change.target_entity.result, UploadResultList
            ):
                return change.target_entity.result
        raise NeatValueError("No outcome found in the provenance.")
