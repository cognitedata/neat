from typing import TypeAlias, TypeVar

from cognite.neat.rules.models import (
    AssetRules,
    DMSRules,
    DomainRules,
    InformationRules,
)
from cognite.neat.rules.models.asset._rules_input import AssetRulesInput
from cognite.neat.rules.models.dms._rules_input import DMSRulesInput
from cognite.neat.rules.models.information._rules_input import InformationRulesInput

VerifiedRules: TypeAlias = DomainRules | InformationRules | DMSRules | AssetRules
InputRules: TypeAlias = AssetRulesInput | DMSRulesInput | InformationRulesInput
Rules: TypeAlias = (
    AssetRulesInput | DMSRulesInput | InformationRulesInput | DomainRules | InformationRules | DMSRules | AssetRules
)
T_Rules = TypeVar("T_Rules", bound=Rules)
