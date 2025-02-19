import pytest

from cognite.neat._utils.text import to_camel_case


class TestToCamel:
    @pytest.mark.parametrize(
        "actual, expected",
        [
            ("TAG_NAME", "tagName"),
            ("TAG NAME", "tagName"),
            ("a_b", "aB"),
            ("Work Order ID", "workOrderID"),
            ("camelCaseAlready", "camelCaseAlready"),
            ("A_-Strange@(Combination)-of#Casing", "aStrangeCombinationOfCasing"),
            ("#SHOUTING@SNAKE_CASE1234", "shoutingSnakeCase1234"),
            ("WO Long Description", "WOLongDescription"),
        ],
    )
    def test_to_camel(self, actual: str, expected: str) -> None:
        assert to_camel_case(actual) == expected
