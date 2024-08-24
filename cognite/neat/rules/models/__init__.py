from cognite.neat.rules.models.asset import AssetRules, AssetRulesInput
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.information._rules import InformationRules
from cognite.neat.rules.models.information._rules_input import InformationRulesInput

from ._base import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from .dms._rules import DMSRules
from .dms._rules_input import DMSRulesInput
from .dms._schema import DMSSchema

RULES_PER_ROLE: dict[RoleTypes, type[DomainRules] | type[InformationRules] | type[AssetRules] | type[DMSRules]] = {
    RoleTypes.domain_expert: DomainRules,
    RoleTypes.information: InformationRules,
    RoleTypes.asset: AssetRules,
    RoleTypes.dms: DMSRules,
}


__all__ = [
    "DomainRules",
    "DMSRulesInput",
    "InformationRulesInput",
    "AssetRulesInput",
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
