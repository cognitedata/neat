from typing import TypeAlias

from cognite.neat.rules.models.rules import DMSRules, DomainRules, InformationRules

Rules: TypeAlias = DomainRules | InformationRules | DMSRules
