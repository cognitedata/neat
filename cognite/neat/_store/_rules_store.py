from datetime import datetime, timezone
from typing import cast

from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer

from ._provenance import UNKNOWN_AGENT, Activity, Change, Entity, ModelEntity, Provenance


class NeatRulesStore:
    def __init__(self):
        self._provenance = Provenance()

    def write(self, importer: BaseImporter) -> IssueList:
        start = datetime.now(timezone.utc)
        issue_list = IssueList()
        with catch_issues(issue_list) as _:
            input_rules = importer.to_rules()
        end = datetime.now(timezone.utc)
        issue_list.extend(input_rules.issues)

        agent = importer.agent
        source_entity = Entity(
            was_attributed_to=UNKNOWN_AGENT,
            id_=importer.source_uri,
        )
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        target_entity = ModelEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=input_rules,
        )

        change = Change(
            agent=importer.agent,
            activity=activity,
            target_entity=target_entity,
            description=importer.description,
            source_entity=source_entity,
        )
        self._provenance.append(change)
        return issue_list

    def transform(self, transformer: RulesTransformer) -> IssueList:
        raise NotImplementedError()

    def read(self, exporter: BaseExporter) -> IssueList:
        raise NotImplementedError()

    def _run(self) -> IssueList:
        raise NotImplementedError()

    def get_last_entity(self) -> ModelEntity:
        if not self._provenance:
            raise NeatValueError("No entity found in the provenance.")
        return cast(ModelEntity, self._provenance[-1].target_entity)
