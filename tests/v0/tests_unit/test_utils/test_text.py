import pytest

from cognite.neat.v0.core._utils.text import NamingStandardization, to_camel_case, to_words


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


class TestToWords:
    @pytest.mark.parametrize(
        "input_, expected",
        [
            ("tagName", "tag name"),
            ("aB", "a b"),
            ("workOrderID", "work order id"),
            ("camelCaseAlready", "camel case already"),
            ("a_Strange_CombinationOfCasing", "a strange combination of casing"),
            ("shouting_snake_case_1234", "shouting snake case 1234"),
        ],
    )
    def test_to_words(self, input_: str, expected: list[str]) -> None:
        assert to_words(input_) == expected


class TestNamingStandardization:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("long" * 43, ("long" * 43)[:43]),
            ("space", "my_space"),
            ("1_my_space", "sp_1_my_space"),
            ("my-$@#@#-space", "my_space"),
        ],
    )
    def test_space_standardization(self, raw: str, expected: str) -> None:
        assert NamingStandardization.standardize_space_str(raw) == expected
