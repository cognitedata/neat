from typing import TypeAlias

from cognite.neat.rules.models import AssetRules, DMSRules, DomainRules, InformationRules

Rules: TypeAlias = DomainRules | InformationRules | DMSRules | AssetRules
