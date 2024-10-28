from cognite.neat._rules.models.asset._rules import AssetRules
from cognite.neat._rules.models.asset._rules_input import AssetInputRules
from cognite.neat._rules.models.domain import DomainInputRules, DomainRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

from ._base_rules import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetList, SheetRow
from .dms._rules import DMSRules
from .dms._rules_input import DMSInputRules
from .dms._schema import DMSSchema

INPUT_RULES_BY_ROLE: dict[
    RoleTypes, type[InformationInputRules] | type[AssetInputRules] | type[DMSInputRules] | type[DomainInputRules]
] = {
    RoleTypes.domain_expert: DomainInputRules,
    RoleTypes.information: InformationInputRules,
    RoleTypes.asset: AssetInputRules,
    RoleTypes.dms: DMSInputRules,
}
VERIFIED_RULES_BY_ROLE: dict[
    RoleTypes, type[InformationRules] | type[AssetRules] | type[DMSRules] | type[DomainRules]
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
    "SheetRow",
]
