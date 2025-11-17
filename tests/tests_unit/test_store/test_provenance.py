from datetime import datetime

from cognite.neat._issues import IssueList, ModelSyntaxError, Recommendation
from cognite.neat._state_machine import PhysicalState
from cognite.neat._store._store import Change


class TestChange:
    def test_as_mixpanel_event(self) -> None:
        change = Change(
            agent="TestAgent",
            activity="TestActivity",
            source_state=PhysicalState(),
            start=datetime(2024, 1, 1, 12, 0, 0),
            end=datetime(2024, 1, 1, 12, 5, 0),
            target_state=PhysicalState(),
            source_entity="SourceEntity",
            target_entity="TargetEntity",
            issues=IssueList(
                [
                    Recommendation(message="some message", code="REC001"),
                    Recommendation(message="some message", code="REC002"),
                ],
            ),
            errors=IssueList([ModelSyntaxError(message="error message", code="ERR001")]),
        )
        event = change.as_mixpanel_event()
        assert {
            "activity": "TestActivity",
            "agent": "TestAgent",
            "duration_ms": 300000,
            "errors": ["ERR001"],
            "issues": ["REC001", "REC002"],
            "sourceEntity": "SourceEntity",
            "sourceState": "PhysicalState",
            "successful": False,
            "targetEntity": "TargetEntity",
            "targetState": "PhysicalState",
        } == event
