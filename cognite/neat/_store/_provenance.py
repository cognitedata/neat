from collections import UserList
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cognite.neat._data_model.deployer.data_classes import DeploymentResult
from cognite.neat._issues import IssueList
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
    issues: IssueList | None = field(default=None)
    errors: IssueList | None = field(default=None)
    # for time being setting to Any, can be refined later
    result: DeploymentResult | None = field(default=None)
    description: str | None = field(default=None)

    @staticmethod
    def standardize_activity_name(activity: str, start: datetime, end: datetime) -> str:
        """Create standardized activity name"""
        return f"{activity}_{start.timestamp()}-{end.timestamp()}"

    @property
    def successful(self) -> bool:
        """Check if change was successful"""
        return not self.errors


class Provenance(UserList[Change]):
    def __delitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Cannot delete change from provenance")

    def __setitem__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Cannot modify change from provenance")

    @property
    def last_change(self) -> Change | None:
        return self[-1] if len(self) > 0 else None

    def can_agent_do_activity(self, activity: Any) -> bool:
        "Check if activity can be performed based on provenance"
        raise NotImplementedError("Not implemented yet")

    def provenance_without_failures(self) -> "Provenance":
        """This method removes all the failed changes from the provenance list."""
        raise NotImplementedError("Not implemented yet")
