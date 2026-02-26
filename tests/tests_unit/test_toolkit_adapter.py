from cognite.neat._toolkit_adapter import (
    DMSAPIImporter,
    DmsDataModelRulesOrchestrator,
    NeatClient,
    NeatConsistencyError,
    NeatModelSyntaxError,
    NeatRecommendation,
    SchemaLimits,
    SchemaSnapshot,
    __all__,
)


class TestToolkitAdapterImports:
    """Test that all expected exports are available from the toolkit adapter module."""

    def test_dms_api_importer_is_importable(self) -> None:
        assert DMSAPIImporter is not None

    def test_dms_data_model_rules_orchestrator_is_importable(self) -> None:
        assert DmsDataModelRulesOrchestrator is not None

    def test_neat_client_is_importable(self) -> None:
        assert NeatClient is not None

    def test_neat_consistency_error_is_importable(self) -> None:
        assert NeatConsistencyError is not None

    def test_neat_model_syntax_error_is_importable(self) -> None:
        assert NeatModelSyntaxError is not None

    def test_neat_recommendation_is_importable(self) -> None:
        assert NeatRecommendation is not None

    def test_schema_snapshot_is_importable(self) -> None:
        assert SchemaSnapshot is not None

    def test_schema_limits_is_importable(self) -> None:
        assert SchemaLimits is not None

    def test_all_exports_are_defined(self) -> None:
        expected_exports = [
            "DMSAPIImporter",
            "DmsDataModelRulesOrchestrator",
            "NeatConsistencyError",
            "NeatModelSyntaxError",
            "NeatRecommendation",
            "SchemaSnapshot",
            "SchemaLimits",
            "NeatClient",
        ]
        assert set(__all__) == set(expected_exports)
