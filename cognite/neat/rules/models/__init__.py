from cognite.neat.rules.models.domain_rules import DomainRules
from cognite.neat.rules.models.information._information_rules import InformationRules

from ._base import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from .dms._dms_architect_rules import DMSRules
from .dms._dms_schema import DMSSchema

RULES_PER_ROLE: dict[RoleTypes, type[DomainRules] | type[InformationRules] | type[DMSRules]] = {
    RoleTypes.domain_expert: DomainRules,
    RoleTypes.information_architect: InformationRules,
    RoleTypes.dms_architect: DMSRules,
}


__all__ = [
    "DomainRules",
    "InformationRules",
    "DMSRules",
    "RULES_PER_ROLE",
    "DMSSchema",
    "RoleTypes",
    "SchemaCompleteness",
    "ExtensionCategory",
    "DataModelType",
    "SheetList",
    "SheetEntity",
]
