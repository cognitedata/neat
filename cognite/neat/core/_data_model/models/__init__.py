from cognite.neat.core._client.data_classes.schema import DMSSchema
from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)

from ._base_verified import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetList, SheetRow
from .dms._rules import DMSRules
from .dms._rules_input import DMSInputRules

INPUT_RULES_BY_ROLE: dict[RoleTypes, type[UnverifiedConceptualDataModel] | type[DMSInputRules]] = {
    RoleTypes.information: UnverifiedConceptualDataModel,
    RoleTypes.dms: DMSInputRules,
}
VERIFIED_RULES_BY_ROLE: dict[RoleTypes, type[ConceptualDataModel] | type[DMSRules]] = {
    RoleTypes.information: ConceptualDataModel,
    RoleTypes.dms: DMSRules,
}


__all__ = [
    "INPUT_RULES_BY_ROLE",
    "ConceptualDataModel",
    "DMSInputRules",
    "DMSRules",
    "DMSSchema",
    "DataModelType",
    "ExtensionCategory",
    "RoleTypes",
    "SchemaCompleteness",
    "SheetList",
    "SheetRow",
    "UnverifiedConceptualDataModel",
]
