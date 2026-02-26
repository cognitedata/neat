"""Module used to safeguard against potential changes in the neat code based that can impact Toolkit implementation.
The module should be used in the Toolkit implementation, and any breaking change in the Neat codebase should be
reflected in this module as well, to ensure that the Toolkit implementation is not broken without noticing."""

from cognite.neat._client import NeatClient
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.rules.dms import DmsDataModelRulesOrchestrator
from cognite.neat._issues import ConsistencyError as NeatConsistencyError
from cognite.neat._issues import ModelSyntaxError as NeatModelSyntaxError
from cognite.neat._issues import Recommendation as NeatRecommendation

__all__ = [
    "DMSAPIImporter",
    "DmsDataModelRulesOrchestrator",
    "NeatClient",
    "NeatConsistencyError",
    "NeatModelSyntaxError",
    "NeatRecommendation",
    "SchemaLimits",
    "SchemaSnapshot",
]
