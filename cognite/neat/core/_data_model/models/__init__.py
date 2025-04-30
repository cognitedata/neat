from cognite.neat.core._client.data_classes.schema import DMSSchema
from cognite.neat.core._data_model.models.conceptual._unvalidate_data_model import (
    ConceptualUnvalidatedDataModel,
)
from cognite.neat.core._data_model.models.conceptual._validated_data_model import (
    ConceptualDataModel,
)

from ._base_validated_data_model import (
    DataModelType,
    ExtensionCategory,
    RoleTypes,
    SchemaCompleteness,
    SheetList,
    SheetRow,
)
from .physical._validated_data_model import DMSRules
from .physical._unvalidated_data_model import DMSInputRules

INPUT_RULES_BY_ROLE: dict[RoleTypes, type[ConceptualUnvalidatedDataModel] | type[DMSInputRules]] = {
    RoleTypes.information: ConceptualUnvalidatedDataModel,
    RoleTypes.dms: DMSInputRules,
}
VERIFIED_RULES_BY_ROLE: dict[RoleTypes, type[ConceptualDataModel] | type[DMSRules]] = {
    RoleTypes.information: ConceptualDataModel,
    RoleTypes.dms: DMSRules,
}


__all__ = [
    "INPUT_RULES_BY_ROLE",
    "ConceptualDataModel",
    "ConceptualUnvalidatedDataModel",
    "DMSInputRules",
    "DMSRules",
    "DMSSchema",
    "DataModelType",
    "ExtensionCategory",
    "RoleTypes",
    "SchemaCompleteness",
    "SheetList",
    "SheetRow",
]
