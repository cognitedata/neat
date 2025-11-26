import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from cognite.neat._issues import ConsistencyError, ModelSyntaxError
from cognite.neat._utils.useful_types import ModusOperandi

if sys.version_info >= (3, 11):
    import tomllib as tomli  # Python 3.11+
else:
    import tomli  # type: ignore


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


INTERNAL_PROFILES = {
    "legacy-additive": ProfileConfig(
        modeling=ProfileModelingConfig(mode="additive"),
        validation=ProfileValidationConfig(
            exclude=[
                "NEAT-DMS-AI-READINESS-*",
                "NEAT-DMS-CONNECTIONS-002",
                "NEAT-DMS-CONNECTIONS-REVERSE-007",
                "NEAT-DMS-CONNECTIONS-REVERSE-008",
                "NEAT-DMS-CONSISTENCY-001",
            ]
        ),
    ),
    "legacy-rebuild": ProfileConfig(
        modeling=ProfileModelingConfig(mode="rebuild"),
        validation=ProfileValidationConfig(
            exclude=[
                "NEAT-DMS-AI-READINESS-*",
                "NEAT-DMS-CONNECTIONS-002",
                "NEAT-DMS-CONNECTIONS-REVERSE-007",
                "NEAT-DMS-CONNECTIONS-REVERSE-008",
                "NEAT-DMS-CONSISTENCY-001",
            ]
        ),
    ),
    "deep-additive": ProfileConfig(
        modeling=ProfileModelingConfig(mode="additive"),
        validation=ProfileValidationConfig(exclude=[]),
    ),
    "deep-rebuild": ProfileConfig(
        modeling=ProfileModelingConfig(mode="rebuild"),
        validation=ProfileValidationConfig(exclude=[]),
    ),
}


class NeatConfig(BaseModel, populate_by_name=True):
    """Main NEAT configuration."""

    profile: str = Field(default="legacy-additive")
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    modeling: ModelingConfig = Field(default_factory=ModelingConfig)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    @field_validator("profiles", mode="before")
    @classmethod
    def _check_if_internal_profiles_are_redifned(cls, value: Any) -> Any | None:
        """Checks that no internal profiles are redefined in the configuration."""

        if redefined := set(INTERNAL_PROFILES.keys()).intersection(value.keys()):
            raise ValueError(f"Internal profiles redefined in external TOML file: {redefined}")

        return value

    def model_post_init(self, __context: Any) -> None:
        """Add profile to profiles dictionary."""

        # add internal profiles
        for profile, config in INTERNAL_PROFILES.items():
            self.profiles[profile] = config

        # Add current profile if not internal
        if self.profile not in INTERNAL_PROFILES:
            self.profiles[self.profile] = ProfileConfig(
                validation=ProfileValidationConfig(exclude=self.validation.exclude.copy()),
                modeling=ProfileModelingConfig(mode=self.modeling.mode),
            )

        # Need to apply profile after all profiles are loaded
        self._apply_profile(self.profile)

    def _apply_profile(self, profile: str) -> None:
        """Apply governance profile configuration."""
        # Check if profile is defined in TOML
        if profile in self.profiles:
            config = self.profiles[profile]
            self.profile = profile
            self.modeling.mode = config.modeling.mode
            self.validation.exclude = config.validation.exclude
            return None

        raise ValueError(f"Unknown profile: {profile}")

    @classmethod
    def load(cls, file_path: Path) -> "NeatConfig":
        """Load configuration from file.

        Args:
            file_path: Path to configuration file.

        Returns:
            NeatConfig instance with loaded or default configuration.
        """

        with file_path.open("rb") as f:
            toml = tomli.load(f)

        if "tool" in toml and "neat" in toml["tool"]:
            data = toml["tool"]["neat"]
        elif "neat" in toml:
            data = toml["neat"]
        else:
            raise ValueError("No [tool.neat] or [neat] section found in the configuration file.")

        if (profile := data.get("profile")) and profile in INTERNAL_PROFILES:
            raise ValueError(f"Internal profile '{profile}' cannot be used in external configuration file.")

        if (profiles := data.get("profiles")) and any(p in INTERNAL_PROFILES for p in profiles.keys()):
            raise ValueError(
                "Internal profiles cannot be redefined in external configuration file: "
                f"{set(INTERNAL_PROFILES.keys()).intersection(profiles.keys())}"
            )

        return cls(**data)

    def __str__(self) -> str:
        """Human-readable configuration summary."""
        lines = [
            f"Profile: {self.profile}",
            f"Modeling Mode: {self.modeling.mode}",
            f"Validation: {self.validation}",
        ]
        return "\n".join(lines)
