from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.neat._issues import IssueList
from cognite.neat._store import NeatGraphStore, NeatRulesStore
from cognite.neat._utils.upload import UploadResultList

from .exceptions import NeatSessionError


class SessionState:
    def __init__(self, store_type: Literal["memory", "oxigraph"]) -> None:
        self.instances = InstancesState(store_type)
        self.rule_store = NeatRulesStore()


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
