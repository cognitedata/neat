from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat._issues import IssueList
from cognite.neat._rules.importers import BaseImporter, InferenceImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.transformers import RulesTransformer, ToExtensionModel
from cognite.neat._store import NeatGraphStore, NeatRulesStore
from cognite.neat._store._rules_store import ModelEntity
from cognite.neat._utils.rdf_ import uri_display_name
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.upload import UploadResultList

from .exceptions import NeatSessionError


class SessionState:
    def __init__(self, store_type: Literal["memory", "oxigraph"]) -> None:
        self.instances = InstancesState(store_type)
        self.rule_store = NeatRulesStore()
        self.last_reference: DMSRules | InformationRules | None = None

    def rule_transform(self, *transformer: RulesTransformer) -> IssueList:
        if not transformer:
            raise NeatSessionError("No transformers provided.")
        first_transformer = transformer[0]
        pruned = self.rule_store.prune_until_compatible(first_transformer)
        if pruned:
            type_hint = first_transformer.transform_type_hint()
            action = uri_display_name(first_transformer.agent.id_)
            location = cast(ModelEntity, self.rule_store.provenance[-1].target_entity).display_name
            expected = humanize_collection([hint.display_type_name() for hint in type_hint])  # type: ignore[attr-defined]
            step_str = "step" if len(pruned) == 1 else "steps"
            print(
                f"The {action} actions expects a {expected}. "
                f"Moving back {len(pruned)} {step_str} to the last {location}."
            )
        if (
            any(isinstance(t, ToExtensionModel) for t in transformer)
            and isinstance(self.rule_store.provenance[-1].target_entity, ModelEntity)
            and isinstance(self.rule_store.provenance[-1].target_entity.result, DMSRules | InformationRules)
        ):
            self.last_reference = self.rule_store.provenance[-1].target_entity.result

        start = cast(ModelEntity, self.rule_store.provenance[-1].target_entity).display_name
        issues = self.rule_store.transform(*transformer)
        end = cast(ModelEntity, self.rule_store.provenance[-1].target_entity).display_name
        issues.action = f"{start} &#8594; {end}"
        issues.hint = "Use the .inspect.issues() for more details."
        return issues

    def rule_import(self, importer: BaseImporter) -> IssueList:
        issues = self.rule_store.import_(importer)
        result = cast(ModelEntity, self.rule_store.provenance[-1].target_entity).display_name
        if isinstance(importer, InferenceImporter):
            issues.action = f"Inferred {result}"
        else:
            issues.action = f"Read {result}"
        if issues:
            issues.hint = "Use the .inspect.issues() for more details."
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
                self._store = NeatGraphStore.from_oxi_store()
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
