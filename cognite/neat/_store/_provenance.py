from typing import Any

from cognite.neat._session._state_machine import State


class Change:
    # base prov-o components
    agent: str
    activity: str
    source_entity: str
    target_entity: str

    # extension of prov-o
    issues: list[str]  # this will be replaced with the actual IssueList

    # relating provenance with state machine
    source_state: State
    target_state: State
    description: str


class Provenance(list, Change):
    def __delitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Cannot delete change from provenance")

    def __setitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Cannot modify change from provenance")
