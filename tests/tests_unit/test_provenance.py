from datetime import datetime
from typing import cast

import pytest

from cognite.neat import _state_machine as states
from cognite.neat._issues import IssueList, ModelSyntaxError
from cognite.neat._store._provenance import Change, Provenance


class TestChange:
    def test_standardize_activity_name(self) -> None:
        start = datetime(2023, 1, 1, 12, 0, 0)
        end = datetime(2023, 1, 1, 12, 1, 0)

        result = Change.standardize_activity_name("test_activity", start, end)
        expected = f"test_activity_{start.timestamp()}-{end.timestamp()}"

        assert result == expected


class TestProvenance:
    def test_empty_provenance(self) -> None:
        provenance = Provenance()
        assert len(provenance) == 0
        assert provenance.last_change is None

    def test_append_change(self) -> None:
        provenance = Provenance()
        change = Change(
            agent="test_agent",
            activity="test_activity",
            source_state=states.EmptyState(),
            start=datetime.now(),
            end=datetime.now(),
        )

        provenance.append(change)
        assert len(provenance) == 1
        assert provenance[0] == change

    def test_last_issues_property(self) -> None:
        provenance = Provenance()
        issues: IssueList = IssueList([ModelSyntaxError(message="error1"), ModelSyntaxError(message="error2")])
        change = Change(
            agent="test_agent",
            activity="test_activity",
            source_state=states.EmptyState(),
            start=datetime.now(),
            end=datetime.now(),
            issues=issues,
        )

        provenance.append(change)
        assert cast(Change, provenance.last_change).issues == issues

    def test_cannot_delete_item(self) -> None:
        provenance = Provenance()
        change = Change(
            agent="test_agent",
            activity="test_activity",
            source_state=states.EmptyState(),
            start=datetime.now(),
            end=datetime.now(),
        )
        provenance.append(change)

        with pytest.raises(TypeError, match="Cannot delete change from provenance"):
            del provenance[0]

    def test_cannot_modify_item(self) -> None:
        provenance = Provenance()
        change1 = Change(
            agent="agent1",
            activity="activity1",
            source_state=states.EmptyState(),
            start=datetime.now(),
            end=datetime.now(),
        )
        change2 = Change(
            agent="agent2",
            activity="activity2",
            source_state=states.EmptyState(),
            start=datetime.now(),
            end=datetime.now(),
        )
        provenance.append(change1)

        with pytest.raises(TypeError, match="Cannot modify change from provenance"):
            provenance[0] = change2
