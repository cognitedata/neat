from ._base import RoleTypes
from ._dms_architect_rules import DMSRules
from ._dms_schema import DMSSchema
from ._domain_rules import DomainRules
from ._information_rules import InformationRules

RULES_PER_ROLE: dict[RoleTypes, type[DomainRules] | type[InformationRules] | type[DMSRules]] = {
    RoleTypes.domain_expert: DomainRules,
    RoleTypes.information_architect: InformationRules,
    RoleTypes.dms_architect: DMSRules,
}


__all__ = ["DomainRules", "InformationRules", "DMSRules", "RULES_PER_ROLE", "DMSSchema"]
