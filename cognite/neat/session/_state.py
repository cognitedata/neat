from dataclasses import dataclass, field
from typing import Literal

from cognite.neat.rules._shared import ReadRules
from cognite.neat.rules.models._base_rules import BaseRules
from cognite.neat.store import NeatGraphStore


@dataclass
class SessionState:
    store_type: Literal["memory", "oxigraph"]
    input_rules: list[ReadRules] = field(default_factory=list)
    verified_rules: list[BaseRules] = field(default_factory=list)
    _store: NeatGraphStore | None = field(init=False, default=None)

    @property
    def store(self) -> NeatGraphStore:
        raise NotImplementedError()

    @property
    def input_rule(self) -> ReadRules:
        raise NotImplementedError()

    @property
    def verified_rule(self) -> BaseRules:
        raise NotImplementedError()
