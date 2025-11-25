from pathlib import Path
from unittest.mock import MagicMock, mock_open

from cognite.neat._config import (
    NeatConfig,
    PhysicalConfig,
    PhysicalModelingConfig,
    PhysicalValidationConfig,
)


class TestNeatConfig:
    """Test suite for NeatConfig - governance profiles and configuration loading."""

    def test_default_initialization(self) -> None:
        """Test default NeatConfig initialization."""
        config = NeatConfig()

        assert config.governance_profile == "legacy-additive"
        assert config.physical.modeling.mode == "additive"
        assert config.physical.validation.profile == "legacy"
        assert config.physical.validation.enabled is True
        assert "ModelSyntaxError" in config.physical.validation.issue_types
        assert "ConsistencyError" in config.physical.validation.issue_types
        assert "Recommendation" not in config.physical.validation.issue_types

    def test_legacy_rebuild_profile(self) -> None:
        """Test legacy-rebuild governance profile application."""
        config = NeatConfig(governance_profile="legacy-rebuild")

        assert config.physical.modeling.mode == "rebuild"
        assert config.physical.validation.profile == "legacy"
        assert "ModelSyntaxError" in config.physical.validation.issue_types
        assert "ConsistencyError" in config.physical.validation.issue_types

    def test_deep_additive_profile(self) -> None:
        """Test deep-additive governance profile application."""
        config = NeatConfig(governance_profile="deep-additive")

        assert config.physical.modeling.mode == "additive"
        assert config.physical.validation.profile == "deep"
        assert "ModelSyntaxError" in config.physical.validation.issue_types
        assert "ConsistencyError" in config.physical.validation.issue_types
        assert "Recommendation" in config.physical.validation.issue_types

    def test_deep_rebuild_profile(self) -> None:
        """Test deep-rebuild governance profile application."""
        config = NeatConfig(governance_profile="deep-rebuild")

        assert config.physical.modeling.mode == "rebuild"
        assert config.physical.validation.profile == "deep"
        assert "ModelSyntaxError" in config.physical.validation.issue_types
        assert "ConsistencyError" in config.physical.validation.issue_types
        assert "Recommendation" in config.physical.validation.issue_types

    def test_custom_governance_profile(self) -> None:
        """Test custom governance profile doesn't apply defaults."""
        config = NeatConfig(
            governance_profile="custom",
            physical=PhysicalConfig(
                validation=PhysicalValidationConfig(profile="custom", issue_types=["ModelSyntaxError"]),
                modeling=PhysicalModelingConfig(mode="rebuild"),
            ),
        )

        assert config.governance_profile == "custom"
        assert config.physical.modeling.mode == "rebuild"

    def test_load_from_pyproject_toml_tool_section(self) -> None:
        """Test loading from pyproject.toml [tool.neat] section."""
        toml_content = """
[tool.neat]
governance-profile = "deep-rebuild"

[tool.neat.physical.validation]
enabled = true
profile = "deep"

[tool.neat.physical.modeling]
mode = "rebuild"
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        config = NeatConfig.load(mock_path)
        assert config.governance_profile == "deep-rebuild"
        assert config.physical.modeling.mode == "rebuild"

    def test_apply_governance_profile_updates_validation(self) -> None:
        """Test that applying governance profile updates validation config."""
        config = NeatConfig(governance_profile="legacy-additive")

        # Change to deep profile
        config._apply_governance_profile("deep-rebuild")

        assert config.physical.validation.profile == "deep"
        assert config.physical.modeling.mode == "rebuild"
        assert "Recommendation" in config.physical.validation.issue_types
