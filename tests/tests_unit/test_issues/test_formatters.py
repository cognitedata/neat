import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat.issues import IssueList
from cognite.neat.issues._base import InvalidRowError
from cognite.neat.issues.errors.properties import PropertyNotFoundError
from cognite.neat.issues.errors.resources import MultiplePropertyDefinitionsError
from cognite.neat.issues.formatters import BasicHTML


@pytest.fixture(scope="session")
def issues() -> IssueList:
    return IssueList(
        [
            InvalidRowError(
                sheet_name="Properties",
                column="IsList",
                row=4,
                type="bool_parsing",
                msg="Input should be a valid boolean, unable to interpret input",
                input="Apple",
                url="https://errors.pydantic.dev/2.6/v/bool_parsing",
            ),
            MultiplePropertyDefinitionsError[ContainerId](
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
