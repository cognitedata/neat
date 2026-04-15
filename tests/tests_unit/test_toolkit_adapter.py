from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cognite_toolkit._cdf_tk.commands.build_v2.data_classes import (  # type: ignore[import-untyped]
    BuiltModule,
    ResourceType,
)
from cognite_toolkit._cdf_tk.commands.build_v2.data_classes._build import BuiltResource  # type: ignore[import-untyped]
from cognite_toolkit._cdf_tk.commands.build_v2.data_classes._module import ModuleId  # type: ignore[import-untyped]
from cognite_toolkit._cdf_tk.resource_ios import DataModelIO  # type: ignore[import-untyped]
from cognite_toolkit._cdf_tk.rules._neat import NeatRuleSet  # type: ignore[import-untyped]

from cognite.neat import _toolkit_adapter
from cognite.neat._client import NeatClient
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError, Recommendation
from cognite.neat._toolkit_adapter import DMSAPIImporter, DmsDataModelRulesOrchestrator


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
        "NeatIssueList",
        "NeatConsistencyError",
        "NeatModelSyntaxError",
        "NeatRecommendation",
        "SchemaLimits",
        "SchemaSnapshot",
    }
    assert set(_toolkit_adapter.__all__) == expected_exports


def test_run_toolkit_validation_with_empty_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests that NeatRuleSet.validate() returns empty results when no modules are provided."""
    # The NeatRuleSet.validate() method iterates over BuiltModule resources looking for DataModel resources.
    # Without modules (and without a client), it should simply return no insights.

    # Change to a directory without cdf.toml to avoid toolkit version mismatch error
    monkeypatch.chdir(tmp_path)

    rule = NeatRuleSet(modules=[])

    result = list(rule.validate())

    assert result == []


def test_run_toolkit_validation_with_data_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    valid_dms_toolkit_yaml_format: str,
) -> None:
    """Tests that NeatRuleSet.validate() validates a data model file and returns insights."""
    # Change to a directory without cdf.toml to avoid toolkit version mismatch error
    monkeypatch.chdir(tmp_path)

    # Create the data model directory structure
    data_model_dir = tmp_path / "data_modeling"
    data_model_dir.mkdir()
    data_model_file = data_model_dir / "model.DataModel.yaml"
    data_model_file.write_text(valid_dms_toolkit_yaml_format)

    # Create a mock module with the data model resource
    mock_module_id = ModuleId(id=Path("test_module"), path=tmp_path)
    mock_resource = MagicMock(spec=BuiltResource)
    mock_resource.type = ResourceType(resource_folder=DataModelIO.folder_name, kind=DataModelIO.kind)
    mock_resource.build_path = data_model_file
    mock_resource.identifier = MagicMock()
    mock_resource.identifier.__str__ = lambda x: "test_model"

    mock_module = BuiltModule(module_id=mock_module_id, resources=[mock_resource])

    # Validate without a client - this will run validation and return any issues
    rule = NeatRuleSet(modules=[mock_module])

    result = list(rule.validate())

    # Without a CDF client/snapshot, validation runs but with local-only rules
    # The result depends on the model, but we verify the validation ran without errors
    # and returns a list (could be empty or contain insights)
    assert isinstance(result, list)
