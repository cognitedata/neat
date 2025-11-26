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

        assert config.profile == "legacy-additive"
        assert config.physical.modeling.mode == "additive"
        assert config.physical.validation.enabled is True
        assert "ModelSyntaxError" in config.physical.validation.issue_types
        assert "ConsistencyError" in config.physical.validation.issue_types
        assert "Recommendation" not in config.physical.validation.issue_types

    def test_custom_governance_profile(self) -> None:
        """Test custom governance profile doesn't apply defaults."""
        config = NeatConfig(
            profile="custom",
            physical=PhysicalConfig(
                validation=PhysicalValidationConfig(issue_types=["ModelSyntaxError"]),
                modeling=PhysicalModelingConfig(mode="rebuild"),
            ),
        )

        assert config.profile == "custom"
        assert config.physical.modeling.mode == "rebuild"

    def test_load_from_pyproject_toml_tool_section(self) -> None:
        """Test loading from pyproject.toml [tool.neat] section."""
        toml_content = """
[tool.neat]
profile = "deep-rebuild"

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
        assert config.profile == "deep-rebuild"
        assert config.physical.modeling.mode == "rebuild"
        assert "Recommendation" in config.physical.validation.issue_types

    def test_profile_update_post_validation(self) -> None:
        config = NeatConfig(profile="legacy-additive")

        assert config.physical.modeling.mode == "additive"
        assert "Recommendation" not in config.physical.validation.issue_types

        # Change to deep profile
        config._apply_profile("deep-rebuild")

        assert config.physical.modeling.mode == "rebuild"
        assert "Recommendation" in config.physical.validation.issue_types
