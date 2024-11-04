from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import ReadRules, VerifiedRules
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._store import NeatGraphStore

from .exceptions import NeatSessionError


@dataclass
class SessionState:
    store_type: Literal["memory", "oxigraph"]
    input_rules: list[ReadRules] = field(default_factory=list)
    verified_rules: list[VerifiedRules] = field(default_factory=list)
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
    def input_rule(self) -> ReadRules:
        if not self.input_rules:
            raise NeatSessionError("No input data model available. Try using [bold].read[/bold] to load a data model.")
        return self.input_rules[-1]

    @property
    def information_input_rule(self) -> ReadRules | None:
        if self.input_rules:
            for rule in self.input_rules[::-1]:
                if isinstance(rule.rules, InformationInputRules):
                    return rule
        return None

    @property
    def last_verified_rule(self) -> VerifiedRules:
        if not self.verified_rules:
            raise NeatSessionError(
                "No data model available to verify. Try using  [bold].read[/bold] to load a data model."
            )
        return self.verified_rules[-1]

    @property
    def last_verified_dms_rules(self) -> DMSRules:
        if self.verified_rules:
            for rules in self.verified_rules[::-1]:
                if isinstance(rules, DMSRules):
                    return rules

        raise NeatSessionError(
            'No verified DMS data model. Try using  [bold].convert("DMS")[/bold]'
            " to convert verified information model to verified DMS model."
        )

    @property
    def last_verified_information_rules(self) -> InformationRules:
        if self.verified_rules:
            for rules in self.verified_rules[::-1]:
                if isinstance(rules, InformationRules):
                    return rules

        raise NeatSessionError(
            "No verified information data model. Try using  [bold].verify()[/bold]"
            " to convert unverified information model to verified information model."
        )

    @property
    def has_store(self) -> bool:
        return self._store is not None

    @property
    def has_verified_rules(self) -> bool:
        return bool(self.verified_rules)

    @property
    def last_issues(self) -> IssueList:
        if not self.issue_lists:
            raise NeatSessionError("No issues available. Try using [bold].verify()[/bold] to verify a data model.")
        return self.issue_lists[-1]
