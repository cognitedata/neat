import sys
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from cognite.neat._issues import ConsistencyError, ModelSyntaxError
from cognite.neat._utils.useful_types import ModusOperandi

if sys.version_info >= (3, 11):
    import tomllib as tomli  # Python 3.11+
else:
    import tomli  # type: ignore


# Type aliases
ConfigProfile = Literal["legacy-additive", "legacy-rebuild", "deep-additive", "deep-rebuild", "custom"]

INTERNAL_PROFILES = {
    "legacy-additive": {
        "modeling": "additive",
        "validation": {
            "exclude": [
                "NEAT-DMS-AI-READINESS-*",
                "NEAT-DMS-CONNECTIONS-002",
                "NEAT-DMS-CONNECTIONS-REVERSE-007",
                "NEAT-DMS-CONNECTIONS-REVERSE-008",
                "NEAT-DMS-CONSISTENCY-001",
            ]
        },
    },
    "legacy-rebuild": {
        "modeling": "rebuild",
        "validation": {
            "exclude": [
                "NEAT-DMS-AI-READINESS-*",
                "NEAT-DMS-CONNECTIONS-002",
                "NEAT-DMS-CONNECTIONS-REVERSE-007",
                "NEAT-DMS-CONNECTIONS-REVERSE-008",
                "NEAT-DMS-CONSISTENCY-001",
            ]
        },
    },
    "deep-additive": {
        "modeling": "additive",
        "validation": {"exclude": []},
    },
    "deep-rebuild": {
        "modeling": "rebuild",
        "validation": {"exclude": []},
    },
}


class ValidationConfig(BaseModel, populate_by_name=True):
    """Validation configuration."""

    exclude: list[str] = Field(default_factory=list)

    def can_run_validator(self, code: str, issue_type: type) -> bool:
        """
        Check if a specific validator should run.

        Args:
            code: Validation code (e.g., "NEAT-DMS-CONTAINER-001")
            issue_type: Issue type (e.g., ModelSyntaxError, ConsistencyError, Recommendation)

        Returns:
            True if validator should run, False otherwise
        """

        excluded = self._matches_pattern(code, self.exclude)

        if issue_type in [ModelSyntaxError, ConsistencyError] and excluded:
            print(f"Validator {code} was excluded however it is a critical validator and will still run.")
            return True
        else:
            return not excluded

    def _matches_pattern(self, code: str, patterns: list[str]) -> bool:
        """Check if code matches any pattern (supports wildcards)."""
        for pattern in patterns:
            if "*" in pattern:
                # Split both pattern and code by hyphens
                pattern_parts = pattern.split("-")
                code_parts = code.split("-")

                # Pattern must have same or fewer parts than code
                if len(pattern_parts) > len(code_parts):
                    continue

                # Check if all pattern parts match (allowing wildcards)
                match = True
                for p_part, c_part in zip(pattern_parts, code_parts, strict=False):
                    if p_part != "*" and p_part != c_part:
                        match = False
                        break

                if match:
                    return True
            elif code == pattern:
                return True

        return False

    def __str__(self) -> str:
        """Human-readable configuration summary."""
        if not self.exclude:
            return "All validators enabled"
        return f"Excluded Rules: {', '.join(self.exclude)}"


class ModelingConfig(BaseModel, populate_by_name=True):
    """Modeling configuration."""

    mode: ModusOperandi = "additive"


class ProfileValidationConfig(BaseModel, populate_by_name=True):
    """Validation configuration within a profile."""

    exclude: list[str] = Field(default_factory=list)


class ProfileModelingConfig(BaseModel, populate_by_name=True):
    """Modeling configuration within a profile."""

    mode: ModusOperandi = "additive"


class ProfileConfig(BaseModel, populate_by_name=True):
    """Configuration for a custom profile."""

    validation: ProfileValidationConfig = Field(default_factory=ProfileValidationConfig)
    modeling: ProfileModelingConfig = Field(default_factory=ProfileModelingConfig)


class NeatConfig(BaseModel, populate_by_name=True):
    """Main NEAT configuration."""

    profile: ConfigProfile = Field(default="legacy-additive")
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    modeling: ModelingConfig = Field(default_factory=ModelingConfig)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Apply profile after initialization."""
        if self.profile != "custom":
            self._apply_profile(self.profile)

    def _apply_profile(self, profile: ConfigProfile) -> None:
        """Apply governance profile configuration."""
        # Check if profile is defined in TOML
        if profile in self.profiles:
            config = self.profiles[profile]
            self.profile = profile
            self.modeling.mode = config.modeling.mode
            self.validation.exclude = config.validation.exclude
            return None

        # Fallback to internal defaults
        if profile in INTERNAL_PROFILES:
            profile_data = INTERNAL_PROFILES[profile]
            self.profile = profile
            self.modeling.mode = cast(ModusOperandi, profile_data["modeling"])
            validation_data = cast(dict[str, Any], profile_data["validation"])
            self.validation.exclude = cast(list[str], validation_data["exclude"])
            return None

        raise ValueError(f"Unknown profile: {profile}")

    @classmethod
    def load(cls, config_path: Path | None = None) -> "NeatConfig":
        """Load configuration from file or use defaults.

        Args:
            config_path: Optional path to configuration file.
                        If None, searches for neat.toml or pyproject.toml in current directory.

        Returns:
            NeatConfig instance with loaded or default configuration.
        """
        paths_to_check: list[Path] = []
        if config_path:
            paths_to_check.append(config_path)
        else:
            cwd = Path.cwd()
            paths_to_check.extend([cwd / "neat.toml", cwd / "pyproject.toml"])

        for path in paths_to_check:
            if not path.exists():
                continue

            with path.open("rb") as f:
                data = tomli.load(f)

            # Check for [tool.neat] section
            if "tool" in data and "neat" in data["tool"]:
                return cls(**data["tool"]["neat"])

            # Check for root [neat] section (if not in pyproject.toml)
            if "tool" not in data and "neat" in data:
                return cls(**data["neat"])

            # If we were looking for a specific file, don't continue searching
            if config_path:
                break

        # Return default configuration
        return cls()

    def __str__(self) -> str:
        """Human-readable configuration summary."""
        lines = [
            f"Profile: {self.profile}",
            f"Modeling Mode: {self.modeling.mode}",
            f"Validation: {self.validation}",
        ]
        return "\n".join(lines)
