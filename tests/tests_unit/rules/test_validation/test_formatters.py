import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat.rules import validation
from cognite.neat.rules.validation import IssueList
from cognite.neat.rules.validation.formatters import BasicHTML


@pytest.fixture(scope="session")
def issues() -> IssueList:
    return IssueList(
        [
            validation.InvalidPropertySpecification(
                column="IsList",
                row=4,
                type="bool_parsing",
                msg="Input should be a valid boolean, unable to interpret input",
                input="Apple",
                url="https://errors.pydantic.dev/2.6/v/bool_parsing",
            ),
            validation.MultiNullableDefinitions(
                container=ContainerId("neat", "Flowable"),
                property_name="maxFlow",
                row_numbers={4, 5},
                nullable_definitions={True, False},
            ),
            validation.MissingContainerProperty(
                container=ContainerId("neat", "Flowable"), property="minFlow", referred_by=ViewId("neat", "Pump", "1")
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
