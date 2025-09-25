from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from cognite.neat.v0.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.v0.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)

from ._base_verified import DataModelType, ExtensionCategory, RoleTypes, SchemaCompleteness, SheetList, SheetRow
from .physical._unverified import UnverifiedPhysicalDataModel
from .physical._verified import PhysicalDataModel

UNVERIFIED_DATA_MODEL_BY_ROLE: dict[
    RoleTypes, type[UnverifiedConceptualDataModel] | type[UnverifiedPhysicalDataModel]
] = {
    RoleTypes.information: UnverifiedConceptualDataModel,
    RoleTypes.dms: UnverifiedPhysicalDataModel,
}
VERIFIED_DATA_MODEL_BY_ROLE: dict[RoleTypes, type[ConceptualDataModel] | type[PhysicalDataModel]] = {
    RoleTypes.information: ConceptualDataModel,
    RoleTypes.dms: PhysicalDataModel,
}


__all__ = [
    "UNVERIFIED_DATA_MODEL_BY_ROLE",
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
