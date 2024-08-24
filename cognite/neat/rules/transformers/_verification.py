from abc import ABC

from cognite.neat.rules._shared import T_InputRules, T_VerifiedRules
from cognite.neat.rules.models import (
    AssetRules,
    AssetRulesInput,
    DMSRules,
    DMSRulesInput,
    InformationRules,
    InformationRulesInput,
)

from ._base import MaybeRule, RulesState, RulesTransformer


class VerificationTransformer(RulesTransformer[T_InputRules, T_VerifiedRules], ABC):
    """Base class for all verification transformers."""

    def transform(self, rules: T_InputRules | RulesState[T_InputRules]) -> MaybeRule[T_VerifiedRules]:
        raise NotImplementedError()


class VerifyDMSRules(VerificationTransformer[DMSRulesInput, DMSRules]): ...


class VerifyInformationRules(VerificationTransformer[InformationRulesInput, InformationRules]): ...


class VerifyAssetRules(VerificationTransformer[AssetRulesInput, AssetRules]): ...
