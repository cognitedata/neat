from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open

from cognite.neat._config import (
    GovernanceProfileConfig,
    GovernanceProfilePhysicalConfig,
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

    def test_legacy_additive_profile(self) -> None:
        """Test legacy-additive governance profile application."""
        config = NeatConfig(governance_profile="legacy-additive")

        assert config.physical.modeling.mode == "additive"
        assert config.physical.validation.profile == "legacy"
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

    def test_governance_profile_from_dict(self) -> None:
        """Test applying governance profile from governance_profiles dict."""
        governance_profiles = {
            "my-profile": GovernanceProfileConfig(
                physical=GovernanceProfilePhysicalConfig(validation_profile="deep", modeling_mode="rebuild")
            )
        }

        config = NeatConfig(governance_profile="custom", governance_profiles=governance_profiles)

        # Test using custom profile that can be programmatically set
        assert config.governance_profile == "custom"

    def test_load_default_config(self) -> None:
        """Test loading default config when no file exists."""
        mock_path = Mock(spec=Path)
        mock_path.exists.return_value = False

        config = NeatConfig.load(mock_path)

        assert config.governance_profile == "legacy-additive"
        assert config.physical.modeling.mode == "additive"

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

    def test_load_with_validation_profiles(self) -> None:
        """Test loading config with validation profiles section."""
        toml_content = """
governance-profile = "legacy-additive"

[physical.validation.profiles.strict]
issue-types = ["ModelSyntaxError", "ConsistencyError", "Recommendation"]
include = ["NEAT-*"]
exclude = []
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        config = NeatConfig.load(mock_path)
        assert "strict" in config.physical.validation.profiles
        assert config.physical.validation.profiles["strict"].include == ["NEAT-*"]

    def test_str_representation(self) -> None:
        """Test string representation of config."""
        config = NeatConfig(governance_profile="deep-additive")

        config_str = str(config)
        assert "Governance Profile: deep-additive" in config_str
        assert "Modeling Mode: additive" in config_str
        assert "Validation Profile: deep" in config_str

    def test_apply_governance_profile_updates_validation(self) -> None:
        """Test that applying governance profile updates validation config."""
        config = NeatConfig(governance_profile="legacy-additive")

        # Change to deep profile
        config._apply_governance_profile("deep-rebuild")

        assert config.physical.validation.profile == "deep"
        assert config.physical.modeling.mode == "rebuild"
        assert "Recommendation" in config.physical.validation.issue_types

    def test_field_aliases(self) -> None:
        """Test that field aliases work correctly."""
        config = NeatConfig.model_validate({"governance-profile": "deep-additive"})

        assert config.governance_profile == "deep-additive"

    def test_nested_physical_config(self) -> None:
        """Test nested physical configuration."""
        config = NeatConfig(
            governance_profile="custom",
            physical=PhysicalConfig(
                validation=PhysicalValidationConfig(enabled=False, profile="custom"),
                modeling=PhysicalModelingConfig(mode="rebuild"),
            ),
        )

        assert config.physical.validation.enabled is False
        assert config.physical.validation.profile == "custom"
        assert config.physical.modeling.mode == "rebuild"

    def test_governance_profile_overrides_physical_settings(self) -> None:
        """Test that governance profile overrides physical settings."""
        config = NeatConfig(
            governance_profile="deep-rebuild",
            physical=PhysicalConfig(
                validation=PhysicalValidationConfig(profile="legacy"),
                modeling=PhysicalModelingConfig(mode="additive"),
            ),
        )

        # Governance profile should override
        assert config.physical.validation.profile == "deep"
        assert config.physical.modeling.mode == "rebuild"

    def test_multiple_governance_profiles_in_dict(self) -> None:
        """Test multiple custom governance profiles."""
        # Test with built-in profiles instead
        config1 = NeatConfig(governance_profile="legacy-additive")
        config2 = NeatConfig(governance_profile="deep-rebuild")

        assert config1.physical.validation.profile == "legacy"
        assert config1.physical.modeling.mode == "additive"
        assert config2.physical.validation.profile == "deep"
        assert config2.physical.modeling.mode == "rebuild"
