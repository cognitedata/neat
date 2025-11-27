from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from pyparsing import Iterator

from cognite.neat._config import (
    ModelingConfig,
    NeatConfig,
    ValidationConfig,
    get_neat_config,
)


def load_good_cases() -> Iterator:
    """Parameterized test cases for valid configurations."""

    yield pytest.param(
        """[tool.neat]
profile = "my-legacy"


[tool.neat.modeling]
mode = "additive"

[tool.neat.validation]
exclude = []

""",
        "my-legacy",
        NeatConfig(
            profile="my-legacy",
            modeling=ModelingConfig(mode="additive"),
            validation=ValidationConfig(exclude=[]),
        ),
        id="tool_my_legacy_valid",
    )

    yield pytest.param(
        """[neat]
profile = "my-legacy"


[neat.modeling]
mode = "additive"

[neat.validation]
exclude = []

""",
        "my-legacy",
        NeatConfig(
            profile="my-legacy",
            modeling=ModelingConfig(mode="additive"),
            validation=ValidationConfig(exclude=[]),
        ),
        id="neat_my_legacy_valid",
    )

    yield pytest.param(
        """[tool.neat]
profile = "my-legacy"


[tool.neat.modeling]
mode = "additive"

[tool.neat.validation]
exclude = []

[tool.neat.profiles.my-custom-profile.modeling]
mode = "additive"

[tool.neat.profiles.my-custom-profile.validation]
exclude = ["NEAT-DMS-AI-READINESS-*", "NEAT-DMS-CONNECTIONS-REVERSE-008"]

""",
        "my-custom-profile",
        NeatConfig(
            profile="my-custom-profile",
            modeling=ModelingConfig(mode="additive"),
            validation=ValidationConfig(exclude=["NEAT-DMS-AI-READINESS-*", "NEAT-DMS-CONNECTIONS-REVERSE-008"]),
        ),
        id="custom_profile_valid",
    )


def load_raises_error_cases() -> Iterator:
    """Parameterized test cases for invalid configurations."""

    yield pytest.param(
        """
[neat]
profile = "legacy-additive"

[neat.validation]
exclude = []
""",
        "legacy-additive",
        "Internal profile 'legacy-additive' cannot be used",
        id="internal_profile_used",
    )

    yield pytest.param(
        """
[neat]
profile = "custom"

[neat.profiles.deep-rebuild.modeling]
mode = "additive"

[neat.profiles.deep-rebuild.validation]
exclude = ["NEAT-DMS-CUSTOM-*"]
""",
        "custom",
        "Internal profiles cannot be redefined",
        id="internal_profile_redefined",
    )

    yield pytest.param(
        """
[other]
some_key = "some_value"

[other.config]
mode = "test"
""",
        "whatever",
        "No \\[tool.neat\\] or \\[neat\\] section found",
        id="missing_neat_section",
    )


def patterns() -> Iterator:
    yield pytest.param(
        "NEAT-DMS-AI-READINESS-001",
        ["NEAT-DMS-AI-READINESS-001"],
        True,
        id="exact_match",
    )
    yield pytest.param(
        "NEAT-DMS-AI-READINESS-001",
        ["NEAT-DMS-AI-READINESS-*"],
        True,
        id="group_match",
    )

    yield pytest.param(
        "NEAT-DMS-AI-READINESS-001",
        ["NEAT-DMS-*"],
        True,
        id="entire_object_validation_exclude",
    )

    yield pytest.param(
        "NEAT-DMS-AI-READINESS-001",
        ["NEAT-DMS-CONNECTIONS-002"],
        False,
        id="passing_match",
    )


class TestNeatConfig:
    @pytest.mark.parametrize(
        "toml_content,profile,error_match",
        list(load_raises_error_cases()),
    )
    def test_load_raises_error(self, toml_content: str, profile: str, error_match: str) -> None:
        """Test that invalid TOML configurations raise ValueError."""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        with patch("cognite.neat._config.Path") as mock_path_class:
            # Mock Path.cwd() to return a mock that creates mock_path when divided
            mock_cwd = MagicMock()
            mock_cwd.__truediv__ = MagicMock(return_value=mock_path)
            mock_path_class.cwd.return_value = mock_cwd

            with pytest.raises(ValueError, match=error_match):
                _ = get_neat_config("neat_config.toml", profile)

    @pytest.mark.parametrize(
        "toml_content,profile,expected_config",
        list(load_good_cases()),
    )
    def test_load_valid_config(self, toml_content: str, profile: str, expected_config: NeatConfig) -> None:
        """Test that valid TOML configurations are loaded correctly."""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open = mock_open(read_data=toml_content.encode())
        mock_path.open.return_value.__enter__.return_value.read.return_value = toml_content.encode()

        with patch("cognite.neat._config.Path") as mock_path_class:
            # Mock Path.cwd() to return a mock that creates mock_path when divided
            mock_cwd = MagicMock()
            mock_cwd.__truediv__ = MagicMock(return_value=mock_path)
            mock_path_class.cwd.return_value = mock_cwd

            config = get_neat_config("neat_config.toml", profile)
            assert config == expected_config

    @pytest.mark.parametrize(
        "code,patterns,expected",
        list(patterns()),
    )
    def test_code_exlucded(self, code: str, patterns: list[str], expected: bool) -> None:
        assert ValidationConfig._is_excluded(code, patterns) == expected
