import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.errors import (
    PropertyDefinitionDuplicatedError,
    PropertyNotFoundError,
)
from cognite.neat.v0.core._issues.formatters import BasicHTML


@pytest.fixture(scope="session")
def issues() -> IssueList:
    return IssueList(
        [
            PropertyDefinitionDuplicatedError[ContainerId](
                ContainerId("neat", "Flowable"),
                "Container",
                "maxFlow",
                frozenset({True, False}),
                (4, 5),
                location_name="rows",
            ),
            PropertyNotFoundError(
                ContainerId("neat", "Flowable"),
                "Container",
                "minFlow",
                ViewId("neat", "Pump", "1"),
                "View",
            ),
        ],
        title="Test title",
    )


class TestBasicHTMLFormatter:
    def test_create_report(self, issues: IssueList):
        formatter = BasicHTML()
        report = formatter.create_report(issues)

        assert "Test title" in report
        assert "Errors" in report
