from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import ReadRules, VerifiedRules
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._store import NeatGraphStore
from cognite.neat._store._provenance import Change, Provenance

from .exceptions import NeatSessionError


class SessionState:
    def __init__(self, store_type: Literal["memory", "oxigraph"]) -> None:
        self.instances = InstancesState(store_type)
        self.data_model = DataModelState()


@dataclass
class InstancesState:
    store_type: Literal["memory", "oxigraph"]
    issue_lists: list[IssueList] = field(default_factory=list)
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


@dataclass
class DataModelState:
    unverified_rules: OrderedDict[str, ReadRules] = field(default_factory=OrderedDict)
    verified_rules: OrderedDict[str, VerifiedRules] = field(default_factory=OrderedDict)
    issue_lists: list[IssueList] = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance)

    @property
    def last_unverified_rule(self) -> ReadRules:
        if not self.unverified_rules:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to load a data model.")
        return next(reversed(self.unverified_rules.values()))

    @property
    def information_unverified_rule(self) -> ReadRules:
        if self.unverified_rules:
            for rule in reversed(self.unverified_rules.values()):
                if isinstance(rule.rules, InformationInputRules):
                    return rule

        raise NeatSessionError("No data model available. Try using [bold].read[/bold] to load a data model.")

    @property
    def last_verified_rule(self) -> VerifiedRules:
        if not self.verified_rules:
            raise NeatSessionError(
                "No data model available to verify. Try using  [bold].read[/bold] to load a data model."
            )
        return next(reversed(self.verified_rules.values()))

    @property
    def last_verified_dms_rules(self) -> DMSRules:
        if self.verified_rules:
            for rules in reversed(self.verified_rules.values()):
                if isinstance(rules, DMSRules):
                    return rules

        raise NeatSessionError(
            'No verified DMS data model. Try using  [bold].convert("DMS")[/bold]'
            " to convert verified information model to verified DMS model."
        )

    @property
    def last_verified_information_rules(self) -> InformationRules:
        if self.verified_rules:
            for rules in reversed(self.verified_rules.values()):
                if isinstance(rules, InformationRules):
                    return rules

        raise NeatSessionError(
            "No verified information data model. Try using  [bold].verify()[/bold]"
            " to convert unverified information model to verified information model."
        )

    @property
    def has_unverified_rules(self) -> bool:
        return bool(self.unverified_rules)

    @property
    def has_verified_rules(self) -> bool:
        return bool(self.verified_rules)

    @property
    def last_issues(self) -> IssueList:
        if not self.issue_lists:
            raise NeatSessionError("No issues available. Try using [bold].verify()[/bold] to verify a data model.")
        return self.issue_lists[-1]

    def write(self, rules: ReadRules | VerifiedRules, change: Change) -> None:
        if change.target_entity.id_ in self.verified_rules or change.target_entity.id_ in self.unverified_rules:
            raise NeatSessionError(f"Data model <{change.target_entity.id_}> already exists.")

        if isinstance(rules, ReadRules):
            self.unverified_rules[change.target_entity.id_] = rules
        else:
            self.verified_rules[change.target_entity.id_] = rules

        self.provenance.append(change)
