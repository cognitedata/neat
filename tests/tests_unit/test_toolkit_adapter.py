import pytest

from cognite.neat import _toolkit_adapter
from cognite.neat._client import NeatClient
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.rules.dms import DmsDataModelRulesOrchestrator
from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError, Recommendation


@pytest.mark.parametrize(
    "name, original_obj",
    [
        ("DMSAPIImporter", DMSAPIImporter),
        ("DmsDataModelRulesOrchestrator", DmsDataModelRulesOrchestrator),
        ("NeatClient", NeatClient),
        ("NeatConsistencyError", ConsistencyError),
        ("NeatModelSyntaxError", ModelSyntaxError),
        ("NeatRecommendation", Recommendation),
        ("NeatIssueList", IssueList),
        ("SchemaLimits", SchemaLimits),
        ("SchemaSnapshot", SchemaSnapshot),
    ],
)
def test_adapter_exports_correct_object(name: str, original_obj: object) -> None:
    """Tests that the toolkit adapter module exports the correct objects."""
    adapter_obj = getattr(_toolkit_adapter, name)
    assert adapter_obj is original_obj


def test_all_exports_are_defined() -> None:
    """Tests that __all__ in the adapter module is correct."""
    expected_exports = {
        "DMSAPIImporter",
        "DmsDataModelRulesOrchestrator",
        "NeatClient",
        "NeatConsistencyError",
        "NeatModelSyntaxError",
        "NeatRecommendation",
        "SchemaLimits",
        "SchemaSnapshot",
    }
    assert set(_toolkit_adapter.__all__) == expected_exports
