from dataclasses import dataclass, field
from typing import Literal, cast

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
    def last_verified_dms_rules(self) -> DMSRules | None:
        if self.verified_rules:
            for rules in self.verified_rules[::-1]:
                if isinstance(rules, DMSRules):
                    return rules
        return None

    @property
    def last_verified_information_rules(self) -> InformationRules | None:
        if self.verified_rules:
            for rules in self.verified_rules[::-1]:
                if isinstance(rules, InformationRules):
                    return rules
        return None

    @property
    def has_store(self) -> bool:
        return self._store is not None
