from collections import UserList
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cognite.neat._state_machine import State


@dataclass
class Change:
    agent: str
    activity: str
    source_state: State
    start: datetime
    end: datetime

    target_state: State | None = field(default=None)
    source_entity: str | None = field(default="ExternalEntity")
    target_entity: str | None = field(default="FailedEntity")
    issues: list[str] | None = field(default=None)
    description: str | None = field(default=None)

    @staticmethod
    def standardize_activity_name(activity: str, start: datetime, end: datetime) -> str:
        """Create standardized activity name"""
        return f"{activity}_{start.timestamp()}-{end.timestamp()}"


class Provenance(UserList[Change]):
    def __delitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Cannot delete change from provenance")

    def __setitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Cannot modify change from provenance")

    @property
    def last_state(self) -> State | None:
        return self[-1].target_state if len(self) > 0 else None

    @property
    def last_issues(self) -> list[str] | None:
        return self[-1].issues if len(self) > 0 else None

    def can_agent_do_activity(self, activity: Any) -> bool:
        "Check if activity can be performed based on provenance"
        return True

    def remove_failed_change(self) -> None:
        """This method removes all the failed changes from the provenance list."""
        raise NotImplementedError("Not implemented yet")
