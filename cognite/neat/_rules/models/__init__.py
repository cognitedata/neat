from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

from ._base_rules import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetList, SheetRow
from .dms._rules import DMSRules
from .dms._rules_input import DMSInputRules
from .dms._schema import DMSSchema

INPUT_RULES_BY_ROLE: dict[RoleTypes, type[InformationInputRules] | type[DMSInputRules]] = {
    RoleTypes.information: InformationInputRules,
    RoleTypes.dms: DMSInputRules,
}
VERIFIED_RULES_BY_ROLE: dict[RoleTypes, type[InformationRules] | type[DMSRules]] = {
    RoleTypes.information: InformationRules,
    RoleTypes.dms: DMSRules,
}


__all__ = [
    "DMSInputRules",
    "InformationInputRules",
    "InformationRules",
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
