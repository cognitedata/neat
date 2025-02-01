import pytest

from cognite.neat._utils.text import to_camel


class TestToCamel:
    @pytest.mark.parametrize(
        "actual, expected",
        [
            ("TAG_NAME", "tagName"),
            ("TAG NAME", "tagName"),
            ("a_b", "aB"),
            ("camel_case", "camelCase"),
        ],
    )
    def test_to_camel(self, actual: str, expected: str) -> None:
        assert to_camel(actual) == expected
