from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat.rules._shared import ReadRules, VerifiedRules, InformationInputRules
from cognite.neat.rules.models import DMSRules, InformationRules
from cognite.neat.store import NeatGraphStore


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
            raise ValueError("No input rules provided")
        return self.input_rules[-1]

    @property
    def information_input_rule(self) -> ReadRules | None:
        if not self.input_rules:
            return None
        for rule in self.input_rules[::-1]:
            if isinstance(rule.rules, InformationInputRules):
                return rule

    @property
    def verified_rule(self) -> VerifiedRules:
        if not self.verified_rules:
            raise ValueError("No verified rules provided")
        return self.verified_rules[-1]

    @property
    def verifies_dms_rules(self) -> DMSRules | None:
        if not self.verified_rules:
            return None

        for rules in self.verified_rules[::-1]:
            if isinstance(rules, DMSRules):
                return rules

    @property
    def verifies_information_rules(self) -> InformationRules | None:
        if not self.verified_rules:
            return None

        for rules in self.verified_rules[::-1]:
            if isinstance(rules, InformationRules):
                return rules

    @property
    def has_store(self) -> bool:
        return self._store is not None
