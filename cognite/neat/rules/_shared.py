from typing import TypeAlias

from cognite.neat.rules.models._rules import DMSRules, DomainRules, InformationRules

Rules: TypeAlias = DomainRules | InformationRules | DMSRules
