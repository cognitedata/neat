import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import PropertyDefinitionDuplicatedError, PropertyNotFoundError, RowError
from cognite.neat._issues.formatters import BasicHTML


@pytest.fixture(scope="session")
def issues() -> IssueList:
    return IssueList(
        [
            RowError(
                sheet_name="Properties",
                column="IsList",
                row=4,
                type="bool_parsing",
                msg="Input should be a valid boolean, unable to interpret input",
                input="Apple",
                url="https://errors.pydantic.dev/2.6/v/bool_parsing",
            ),
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
