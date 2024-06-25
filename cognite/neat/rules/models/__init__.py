from cognite.neat.rules.models.asset import AssetRules
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.information._rules import InformationRules

from ._base import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from .dms._rules import DMSRules
from .dms._schema import DMSSchema

RULES_PER_ROLE: dict[RoleTypes, type[DomainRules] | type[InformationRules] | type[AssetRules] | type[DMSRules]] = {
    RoleTypes.domain_expert: DomainRules,
    RoleTypes.information_architect: InformationRules,
    RoleTypes.asset_architect: AssetRules,
    RoleTypes.dms_architect: DMSRules,
}


__all__ = [
    "DomainRules",
    "InformationRules",
    "AssetRules",
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
