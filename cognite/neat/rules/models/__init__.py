from cognite.neat.rules.models.asset import AssetInputRules, AssetRules
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.information._rules import InformationRules
from cognite.neat.rules.models.information._rules_input import InformationInputRules

from ._base import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetEntity, SheetList
from .dms._rules import DMSRules
from .dms._rules_input import DMSInputRules
from .dms._schema import DMSSchema

INPUT_RULES_BY_ROLE: dict[RoleTypes, type[InformationInputRules] | type[AssetInputRules] | type[DMSInputRules]] = {
    # RoleTypes.domain_expert: DomainRules,
    RoleTypes.information: InformationInputRules,
    RoleTypes.asset: AssetInputRules,
    RoleTypes.dms: DMSInputRules,
}
VERIFIED_RULES_BY_ROLE: dict[
    RoleTypes, type[DomainRules] | type[InformationRules] | type[AssetRules] | type[DMSRules]
] = {
    RoleTypes.domain_expert: DomainRules,
    RoleTypes.information: InformationRules,
    RoleTypes.asset: AssetRules,
    RoleTypes.dms: DMSRules,
}


__all__ = [
    "DomainRules",
    "DMSInputRules",
    "InformationInputRules",
    "AssetInputRules",
    "InformationRules",
    "AssetRules",
    "DMSRules",
    "INPUT_RULES_BY_ROLE",
    "DMSSchema",
    "RoleTypes",
    "SchemaCompleteness",
    "ExtensionCategory",
    "DataModelType",
    "SheetList",
    "SheetEntity",
]
