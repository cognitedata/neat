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
profile = "custom"

[tool.neat.validation]
exclude = []

[tool.neat.modeling]
mode = "rebuild"

[tool.neat.profiles.my-custom-profile.modeling]
mode = "additive"

[tool.neat.profiles.my-custom-profile.validation]
exclude = ["NEAT-DMS-AI-READINESS-*", "NEAT-DMS-CONNECTIONS-REVERSE-008"]
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        config = NeatConfig.load(mock_path)
        assert config.profile == "custom"
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

    def test_load_from_root_neat_section(self) -> None:
        """Test loading from root [neat] section in neat.toml."""
        toml_content = """
[neat]
profile = "custom"

[neat.validation]
exclude = ["NEAT-DMS-TEST-*"]

[neat.modeling]
mode = "additive"
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        config = NeatConfig.load(mock_path)
        assert config.profile == "custom"
        assert config.modeling.mode == "additive"
        assert config.validation.exclude == ["NEAT-DMS-TEST-*"]

    def test_load_with_internal_profile_raises_error(self) -> None:
        """Test that using an internal profile name in TOML raises ValueError."""
        toml_content = """
[neat]
profile = "legacy-additive"

[neat.validation]
exclude = []
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        import pytest

        with pytest.raises(ValueError, match="Internal profile 'legacy-additive' cannot be used"):
            NeatConfig.load(mock_path)

    def test_load_with_redefined_internal_profile_raises_error(self) -> None:
        """Test that redefining an internal profile in TOML raises ValueError."""
        toml_content = """
[neat]
profile = "custom"

[neat.profiles.deep-rebuild.modeling]
mode = "additive"

[neat.profiles.deep-rebuild.validation]
exclude = ["NEAT-DMS-CUSTOM-*"]
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        import pytest

        with pytest.raises(ValueError, match="Internal profiles cannot be redefined"):
            NeatConfig.load(mock_path)

    def test_load_without_neat_section_raises_error(self) -> None:
        """Test that loading TOML without [neat] or [tool.neat] section raises ValueError."""
        toml_content = """
[other]
some_key = "some_value"

[other.config]
mode = "test"
"""

        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        import pytest

        with pytest.raises(ValueError, match="No \\[tool.neat\\] or \\[neat\\] section found"):
            NeatConfig.load(mock_path)
