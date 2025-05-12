from cognite.neat.core._client.data_classes.schema import DMSSchema
from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)

from ._base_verified import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetList, SheetRow
from .physical._unverified import UnverifiedPhysicalDataModel
from .physical._verified import PhysicalDataModel

INPUT_RULES_BY_ROLE: dict[RoleTypes, type[UnverifiedConceptualDataModel] | type[UnverifiedPhysicalDataModel]] = {
    RoleTypes.information: UnverifiedConceptualDataModel,
    RoleTypes.dms: UnverifiedPhysicalDataModel,
}
VERIFIED_RULES_BY_ROLE: dict[RoleTypes, type[ConceptualDataModel] | type[PhysicalDataModel]] = {
    RoleTypes.information: ConceptualDataModel,
    RoleTypes.dms: PhysicalDataModel,
}


__all__ = [
    "INPUT_RULES_BY_ROLE",
    "ConceptualDataModel",
    "DMSSchema",
    "DataModelType",
    "ExtensionCategory",
    "PhysicalDataModel",
    "RoleTypes",
    "SchemaCompleteness",
    "SheetList",
    "SheetRow",
    "UnverifiedConceptualDataModel",
    "UnverifiedPhysicalDataModel",
]
