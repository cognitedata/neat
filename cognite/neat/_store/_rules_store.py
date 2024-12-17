from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import OutRules, T_VerifiedRules
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.exporters._base import T_Export
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer

from ._provenance import UNKNOWN_AGENT, Activity, Agent, Change, Entity, ModelEntity, Provenance


class NeatRulesStore:
    def __init__(self):
        self.provenance = Provenance()

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
                lambda: item.transform(last_entity),  # noqa: B023
                item.agent,
                last_entity,
                item.description,
            )[1]
            all_issues.extend(transform_issues)
        return all_issues

    def export(self, exporter: BaseExporter[T_VerifiedRules, T_Export], path: Path | None = None) -> T_Export:
        last_entity = self.get_last_successful_entity()
        result = last_entity.result
        if not isinstance(result, OutRules):
            raise NeatValueError(f"Expected OutRules, got {type(result)}")
        rules = result.get_rules()

        result, _ = self._run(
            lambda: exporter.export(rules) if path is None else exporter.export_to_file(rules, path),  # type: ignore[arg-type]
            exporter.agent,
            last_entity,
            exporter.description,
        )
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

    def get_last_entity(self) -> ModelEntity:
        if not self.provenance:
            raise NeatValueError("No entity found in the provenance.")
        return cast(ModelEntity, self.provenance[-1].target_entity)

    def get_last_successful_entity(self) -> ModelEntity:
        for change in reversed(self.provenance):
            if isinstance(change.target_entity, ModelEntity) and change.target_entity.result:
                return change.target_entity
        raise NeatValueError("No successful entity found in the provenance.")
