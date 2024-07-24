import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

import cognite.neat.rules.issues.spreadsheet
from cognite.neat.issues import IssueList
from cognite.neat.issues.errors.resources import ReferredResourceNotFoundError
from cognite.neat.issues.formatters import BasicHTML
from cognite.neat.rules import issues as validation


@pytest.fixture(scope="session")
def issues() -> IssueList:
    return IssueList(
        [
            validation.spreadsheet.InvalidPropertyError(
                column="IsList",
                row=4,
                type="bool_parsing",
                msg="Input should be a valid boolean, unable to interpret input",
                input="Apple",
                url="https://errors.pydantic.dev/2.6/v/bool_parsing",
            ),
            cognite.neat.rules.issues.spreadsheet.MultiNullableError(
                container=ContainerId("neat", "Flowable"),
                property_name="maxFlow",
                row_numbers={4, 5},
                nullable_definitions={True, False},
            ),
            ReferredResourceNotFoundError[ContainerId, ViewId](
                ContainerId("neat", "Flowable"),
                "Container",
                ViewId("neat", "Pump", "1"),
                "View",
                property_name="minFlow",
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
