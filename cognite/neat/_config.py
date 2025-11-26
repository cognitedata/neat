import sys
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, field_validator

from cognite.neat._issues import ModelSyntaxError
from cognite.neat._utils.useful_types import ModusOperandi

if sys.version_info >= (3, 11):
    import tomllib as tomli  # Python 3.11+
else:
    import tomli  # type: ignore


# Type aliases
ConfigProfile = Literal["legacy-additive", "legacy-rebuild", "deep-additive", "deep-rebuild", "custom"]
IssueType = Literal["ModelSyntaxError", "ConsistencyError", "Recommendation"]

INTERNAL_PROFILES = {
    "legacy-additive": {"validation": "legacy", "modeling": "additive"},
    "legacy-rebuild": {"validation": "legacy", "modeling": "rebuild"},
    "deep-additive": {"validation": "deep", "modeling": "additive"},
    "deep-rebuild": {"validation": "deep", "modeling": "rebuild"},
}


class PhysicalValidationConfig(BaseModel, populate_by_name=True):
    """Validation configuration for physical data models."""

    enabled: bool = True
    issue_types: list[IssueType] = Field(default=["ConsistencyError", "Recommendation"], alias="issue-types")
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    @staticmethod
    def _add_model_syntax_error(issue_types: list[IssueType]) -> list[IssueType]:
        """Ensures ModelSyntaxError is the first element of the list."""
        if "ModelSyntaxError" not in issue_types:
            issue_types.insert(0, "ModelSyntaxError")
        return issue_types

    @field_validator("issue_types", mode="after")
    @classmethod
    def ensure_syntax_error_included(cls, v: list[IssueType]) -> list[IssueType]:
        """Ensure ModelSyntaxError is always included in issue types."""
        return cls._add_model_syntax_error(v)

    @property
    def effective_issue_types(self) -> list[IssueType]:
        """Get issue types with ModelSyntaxError always included."""
        return self._add_model_syntax_error(list(self.issue_types))

    def apply_legacy_profile(self) -> None:
        """Apply legacy profile (backward compatible with original NEAT)."""
        self.issue_types = ["ModelSyntaxError", "ConsistencyError"]
        self.include = ["NEAT-DMS-*"]
        self.exclude = []

    def apply_deep_profile(self) -> None:
        """Apply deep profile (all validators enabled)."""
        self.issue_types = ["ModelSyntaxError", "ConsistencyError", "Recommendation"]
        self.include = ["NEAT-DMS-*"]
        self.exclude = []

    def can_run_validator(self, code: str, issue_type: type | None = None) -> bool:
        """
        Check if a specific validator should run.

        Args:
            code: Validation code (e.g., "NEAT-DMS-CONTAINER-001")
            issue_type: Optional issue class for additional filtering

        Returns:
            True if validator should run, False otherwise
        """
        if not self.enabled:
            return False

        # ModelSyntaxError is ALWAYS checked
        if issue_type is ModelSyntaxError:
            return True

        # Check explicit exclusions first (highest priority)
        if self._matches_pattern(code, self.exclude):
            return False

        # Check explicit inclusions
        if self.include:
            if not self._matches_pattern(code, self.include):
                return False

        # Check issue type filtering (ModelSyntaxError always passes)
        if issue_type is not None:
            issue_name = issue_type.__name__
            if issue_name != "ModelSyntaxError" and issue_name not in self.effective_issue_types:
                return False

        return True

    def _matches_pattern(self, code: str, patterns: list[str]) -> bool:
        """Check if code matches any pattern (supports wildcards)."""
        for pattern in patterns:
            if "*" in pattern:
                pattern_parts = pattern.split("-")
                code_parts = code.split("-")

                if len(pattern_parts) < len(code_parts):
                    pattern_parts.extend(["*"] * (len(code_parts) - len(pattern_parts)))
                elif len(pattern_parts) > len(code_parts):
                    continue

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
        if not self.enabled:
            lines = ["Validation is disabled."]
        else:
            lines = [
                f"Issue Types: {', '.join(self.effective_issue_types)}",
            ]

            if self.include:
                lines.append(f"Included Rules: {', '.join(self.include)}")

            if self.exclude:
                lines.append(f"Excluded Rules: {', '.join(self.exclude)}")

        return "\n".join(lines)


class PhysicalModelingConfig(BaseModel, populate_by_name=True):
    """Modeling configuration for physical data models."""

    mode: ModusOperandi = "additive"


class PhysicalConfig(BaseModel, populate_by_name=True):
    """Configuration for physical data model operations."""

    validation: PhysicalValidationConfig = Field(default_factory=PhysicalValidationConfig)
    modeling: PhysicalModelingConfig = Field(default_factory=PhysicalModelingConfig)


class ProfilePhysicalValidationConfig(BaseModel, populate_by_name=True):
    """Physical validation configuration within a profile."""

    enabled: bool = True
    issue_types: list[IssueType] = Field(default_factory=list, alias="issue-types")
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class ProfilePhysicalModelingConfig(BaseModel, populate_by_name=True):
    """Physical modeling configuration within a profile."""

    mode: ModusOperandi = "additive"


class ProfilePhysicalConfig(BaseModel, populate_by_name=True):
    """Physical configuration within a governance profile."""

    validation: ProfilePhysicalValidationConfig = Field(default_factory=ProfilePhysicalValidationConfig)
    modeling: ProfilePhysicalModelingConfig = Field(default_factory=ProfilePhysicalModelingConfig)


class ProfileConfig(BaseModel, populate_by_name=True):
    """Configuration for a governance profile."""

    physical: ProfilePhysicalConfig = Field(default_factory=ProfilePhysicalConfig)


class NeatConfig(BaseModel, populate_by_name=True):
    """Main NEAT configuration."""

    profile: ConfigProfile = Field(default="legacy-additive")
    physical: PhysicalConfig = Field(default_factory=PhysicalConfig)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Apply governance profile if not custom."""
        if self.profile != "custom":
            self._apply_profile(self.profile)

    def _apply_profile(self, profile: ConfigProfile) -> None:
        """Apply governance profile to physical configuration."""

        # Predefined profiles from TOML
        if profile in self.profiles:
            config = self.profiles[profile]
            self.profile = profile

            # Apply modeling mode
            self.physical.modeling.mode = config.physical.modeling.mode

            # Apply validation settings
            self.physical.validation.enabled = config.physical.validation.enabled
            self.physical.validation.issue_types = PhysicalValidationConfig._add_model_syntax_error(
                config.physical.validation.issue_types
            )
            self.physical.validation.include = config.physical.validation.include
            self.physical.validation.exclude = config.physical.validation.exclude
            return None

        # Fallback to internal defaults
        if profile in INTERNAL_PROFILES:
            self.profile = profile
            self.physical.modeling.mode = cast(ModusOperandi, INTERNAL_PROFILES[profile]["modeling"])

            # Apply validation based on internal profile type
            validation_type = INTERNAL_PROFILES[profile]["validation"]
            if validation_type == "legacy":
                self.physical.validation.apply_legacy_profile()
            elif validation_type == "deep":
                self.physical.validation.apply_deep_profile()

    @classmethod
    def load(cls, config_path: Path | None = None) -> "NeatConfig":
        """Load configuration from file or use defaults."""

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

            if "tool" in data and "neat" in data["tool"]:
                return cls(**data["tool"]["neat"])

            if "tool" not in data and data:
                return cls(**data)

            if config_path:
                break

        return cls()

    def __str__(self) -> str:
        """Human-readable configuration summary."""
        lines = [
            f"Config Profile: {self.profile}",
            "",
            "Physical Data Model:",
            f"  Modeling Mode: {self.physical.modeling.mode}",
            f"  {self.physical.validation}".replace("\n", "\n  "),
        ]
        return "\n".join(lines)
