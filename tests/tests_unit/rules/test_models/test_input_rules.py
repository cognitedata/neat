import json
from collections.abc import Iterable

import pytest
from _pytest.mark import ParameterSet

from cognite.neat.rules.models._base_input import InputRules
from tests.utils import DataClassCreator, get_all_subclasses


def input_rules_instances_iterator() -> Iterable[ParameterSet]:
    for cls_ in get_all_subclasses(InputRules, only_concrete=True):
        yield pytest.param(DataClassCreator(cls_).create_instance(), id=cls_.__name__)


class TestInputRules:
    def test_input_rules_match_verified_cls(self):
        assert True

    @pytest.mark.parametrize("input_rules", input_rules_instances_iterator())
    def test_issues_dump_load(self, input_rules: InputRules) -> None:
        """Test that all classes that inherit from InputRules can be dumped and loaded."""
        dumped = input_rules.dump()
        assert isinstance(dumped, dict)
        assert dumped != {}, f"Empty dump for {type(input_rules).__name__}"
        # Ensure that the dump can be serialized and deserialized
        json_dumped = json.dumps(dumped)
        json_loaded = json.loads(json_dumped)
        loaded = type(input_rules).load(json_loaded)
        assert input_rules == loaded, f"Dump and load mismatch for {type(input_rules).__name__}"
