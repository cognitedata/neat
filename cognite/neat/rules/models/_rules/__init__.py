from .base import RoleTypes
from .dms_architect_rules import DMSRules
from .dms_schema import DMSSchema
from .domain_rules import DomainRules
from .information_rules import InformationRules

RULES_PER_ROLE: dict[RoleTypes, type[DomainRules] | type[InformationRules] | type[DMSRules]] = {
    RoleTypes.domain_expert: DomainRules,
    RoleTypes.information_architect: InformationRules,
    RoleTypes.dms_architect: DMSRules,
}


__all__ = ["DomainRules", "InformationRules", "DMSRules", "RULES_PER_ROLE", "DMSSchema"]
