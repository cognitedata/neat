import pytest

from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models import DMSInputRules, DMSRules, InformationInputRules, InformationRules
from cognite.neat._rules.transformers import RulesTransformer


class TestRuleTransformer:
    @pytest.mark.parametrize(
        "transformer_cls",
        list(RulesTransformer.__subclasses__()),
    )
    def test_transform_method_valid_signature(self, transformer_cls: type[RulesTransformer]) -> None:
        valid_type_hints = {DMSRules, InformationRules, ReadRules[InformationInputRules], ReadRules[DMSInputRules]}

        type_hint = transformer_cls.transform_type_hint()

        invalid_type_hints = set(type_hint) - valid_type_hints

        assert not invalid_type_hints, f"Invalid type hints: {invalid_type_hints}"
