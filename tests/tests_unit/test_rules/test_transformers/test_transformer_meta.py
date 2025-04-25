from abc import ABC
from collections.abc import Iterable

import pytest

from cognite.neat.core._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.models import (
    DMSInputRules,
    DMSRules,
    InformationInputRules,
    InformationRules,
)
from cognite.neat.core._rules.transformers import (
    AddClassImplements,
    AddCogniteProperties,
    ClassicPrepareCore,
    DropModelViews,
    IncludeReferenced,
    PrefixEntities,
    RuleMapper,
    RulesTransformer,
    SetIDDMSModel,
    ToExtensionModel,
)

TRANSFORMATION_CLASSES = list(RulesTransformer.__subclasses__())


def instantiated_transformers_cls() -> Iterable[RulesTransformer]:
    for transformation_cls in TRANSFORMATION_CLASSES:
        if ABC in transformation_cls.__bases__:
            continue
        if issubclass(transformation_cls, PrefixEntities):
            yield transformation_cls(prefix="test")
        elif issubclass(transformation_cls, SetIDDMSModel | ToExtensionModel):
            yield transformation_cls(("my_space", "my_id", "v1"))
        elif issubclass(transformation_cls, DropModelViews):
            yield transformation_cls("3D")
        elif issubclass(transformation_cls, AddClassImplements):
            yield transformation_cls("Edge", "Edge")
        elif issubclass(transformation_cls, RuleMapper | IncludeReferenced | AddCogniteProperties):
            # Manually checked as these require NeatClient or DMSRules in the setup
            continue
        elif issubclass(transformation_cls, ClassicPrepareCore):
            return ClassicPrepareCore(CLASSIC_CDF_NAMESPACE)
        else:
            yield transformation_cls()


class TestRuleTransformer:
    @pytest.mark.parametrize("transformer_cls", TRANSFORMATION_CLASSES)
    def test_transform_method_valid_signature(self, transformer_cls: type[RulesTransformer]) -> None:
        valid_type_hints = {DMSRules, InformationRules, ReadRules[InformationInputRules], ReadRules[DMSInputRules]}

        type_hint = transformer_cls.transform_type_hint()

        invalid_type_hints = set(type_hint) - valid_type_hints

        assert not invalid_type_hints, f"Invalid type hints: {invalid_type_hints}"

    @pytest.mark.parametrize(
        "transformer", [pytest.param(v, id=type(v).__name__) for v in instantiated_transformers_cls()]
    )
    def test_has_description(self, transformer: RulesTransformer) -> None:
        assert transformer.description != "MISSING DESCRIPTION", f"Missing description for {transformer}"
