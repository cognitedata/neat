from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat.rules._shared import ReadRules, VerifiedRules
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
    def verified_rule(self) -> VerifiedRules:
        if not self.verified_rules:
            raise ValueError("No verified rules provided")
        return self.verified_rules[-1]

    @property
    def has_store(self) -> bool:
        return self._store is not None
