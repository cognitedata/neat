from pathlib import Path
from unittest.mock import MagicMock, mock_open

from cognite.neat._config import (
    ModelingConfig,
    NeatConfig,
    ValidationConfig,
)


class TestNeatConfig:
    """Test suite for NeatConfig - governance profiles and configuration loading."""

    def test_default_initialization(self) -> None:
        """Test default NeatConfig initialization."""
        config = NeatConfig()

        assert config.profile == "legacy-additive"
        assert config.modeling.mode == "additive"
        assert config.validation.exclude == [
            "NEAT-DMS-AI-READINESS-*",
            "NEAT-DMS-CONNECTIONS-002",
            "NEAT-DMS-CONNECTIONS-REVERSE-007",
            "NEAT-DMS-CONNECTIONS-REVERSE-008",
            "NEAT-DMS-CONSISTENCY-001",
        ]

    def test_custom_governance_profile(self) -> None:
        """Test custom governance profile doesn't apply defaults."""
        config = NeatConfig(
            profile="custom",
            validation=ValidationConfig(exclude=["NEAT-DMS-CUSTOM-*"]),
            modeling=ModelingConfig(mode="rebuild"),
        )

        assert config.profile == "custom"
        assert config.modeling.mode == "rebuild"

    def test_load_from_pyproject_toml_tool_section(self) -> None:
        """Test loading from pyproject.toml [tool.neat] section."""
        toml_content = """
[tool.neat]
profile = "deep-rebuild"

[tool.neat.validation]
exclude = []

[tool.neat.modeling]
mode = "rebuild"
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        config = NeatConfig.load(mock_path)
        assert config.profile == "deep-rebuild"
        assert config.modeling.mode == "rebuild"
        assert config.validation.exclude == []

    def test_profile_update_post_validation(self) -> None:
        config = NeatConfig(profile="legacy-additive")

        assert config.modeling.mode == "additive"
        assert len(config.validation.exclude) > 0

        # Change to deep profile
        config._apply_profile("deep-rebuild")

        assert config.modeling.mode == "rebuild"
        assert config.validation.exclude == []
