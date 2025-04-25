from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules

from ._base_rules import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetList, SheetRow
from .dms._rules import DMSRules
from .dms._rules_input import DMSInputRules

INPUT_RULES_BY_ROLE: dict[RoleTypes, type[InformationInputRules] | type[DMSInputRules]] = {
    RoleTypes.information: InformationInputRules,
    RoleTypes.dms: DMSInputRules,
}
VERIFIED_RULES_BY_ROLE: dict[RoleTypes, type[InformationRules] | type[DMSRules]] = {
    RoleTypes.information: InformationRules,
    RoleTypes.dms: DMSRules,
}


__all__ = [
    "INPUT_RULES_BY_ROLE",
    "DMSInputRules",
    "DMSRules",
    "DMSSchema",
    "DataModelType",
    "ExtensionCategory",
    "InformationInputRules",
    "InformationRules",
    "RoleTypes",
    "SchemaCompleteness",
    "SheetList",
    "SheetRow",
]
