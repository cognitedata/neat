from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from cognite.neat._utils.useful_types import ModusOperandi

# Type aliases
ValidationProfile = Literal["legacy", "deep", "custom"]
GovernanceProfile = Literal["legacy-additive", "legacy-rebuild", "deep-additive", "deep-rebuild", "custom"]
IssueType = Literal["ModelSyntaxError", "ConsistencyError", "Recommendation"]


class ValidationProfileConfig(BaseModel):
    """Configuration for a validation profile."""

    issue_types: list[IssueType] = Field(default_factory=list, alias="issue-types")
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class PhysicalValidationConfig(BaseModel):
    """Validation configuration for physical data models."""

    enabled: bool = True
    profile: ValidationProfile = "legacy"
    issue_types: list[IssueType] = Field(default=["ConsistencyError", "Recommendation"], alias="issue-types")
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    # Predefined profiles (loaded from TOML)
    profiles: dict[str, ValidationProfileConfig] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("issue_types", mode="after")
    @classmethod
    def ensure_syntax_error_included(cls, v: list[IssueType]) -> list[IssueType]:
        """Ensure ModelSyntaxError is always included in issue types."""
        if "ModelSyntaxError" not in v:
            v.insert(0, "ModelSyntaxError")
        return v

    @property
    def effective_issue_types(self) -> list[IssueType]:
        """Get issue types with ModelSyntaxError always included."""
        types = list(self.issue_types)
        if "ModelSyntaxError" not in types:
            types.insert(0, "ModelSyntaxError")
        return types

    def model_post_init(self, __context: Any) -> None:
        """Apply profile settings if not using custom profile."""
        if self.profile != "custom":
            self._apply_profile(self.profile)

    def _apply_profile(self, profile: ValidationProfile) -> None:
        """Apply predefined validation profile settings."""
        if profile in self.profiles:
            profile_config = self.profiles[profile]
            self.issue_types = profile_config.issue_types
            # Ensure ModelSyntaxError is always included
            if "ModelSyntaxError" not in self.issue_types:
                self.issue_types.insert(0, "ModelSyntaxError")
            self.include = profile_config.include
            self.exclude = profile_config.exclude
            return

        # Fallback to hardcoded defaults if not in TOML
        if profile == "legacy":
            self._apply_legacy_profile()
        elif profile == "deep":
            self._apply_deep_profile()

    def _apply_legacy_profile(self) -> None:
        """Apply legacy profile (backward compatible with original NEAT)."""
        self.issue_types = ["ModelSyntaxError", "ConsistencyError"]
        self.include = ["NEAT-DMS-*"]
        self.exclude = []

    def _apply_deep_profile(self) -> None:
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

        # Import issue types
        from cognite.neat._issues import ModelSyntaxError

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
        lines = [
            f"Validation Profile: {self.profile}",
            f"Enabled: {self.enabled}",
            f"Issue Types: {', '.join(self.effective_issue_types)}",
        ]

        if self.include:
            lines.append(f"Included Rules: {', '.join(self.include)}")

        if self.exclude:
            lines.append(f"Excluded Rules: {', '.join(self.exclude)}")

        return "\n".join(lines)


class PhysicalModelingConfig(BaseModel):
    """Modeling configuration for physical data models."""

    mode: ModusOperandi = "additive"

    model_config = {"populate_by_name": True}


class PhysicalConfig(BaseModel):
    """Configuration for physical data model operations."""

    validation: PhysicalValidationConfig = Field(default_factory=PhysicalValidationConfig)
    modeling: PhysicalModelingConfig = Field(default_factory=PhysicalModelingConfig)

    model_config = {"populate_by_name": True}


class GovernanceProfilePhysicalConfig(BaseModel):
    """Physical configuration within a governance profile."""

    validation_profile: ValidationProfile = Field(alias="validation-profile")
    modeling_mode: ModusOperandi = Field(alias="modeling-mode")

    model_config = {"populate_by_name": True}


class GovernanceProfileConfig(BaseModel):
    """Configuration for a governance profile."""

    physical: GovernanceProfilePhysicalConfig

    model_config = {"populate_by_name": True}


class NeatConfig(BaseModel):
    """Main NEAT configuration."""

    governance_profile: GovernanceProfile = Field(default="legacy-additive", alias="governance-profile")
    physical: PhysicalConfig = Field(default_factory=PhysicalConfig)
    governance_profiles: dict[str, GovernanceProfileConfig] = Field(default_factory=dict, alias="governance-profiles")

    model_config = {"populate_by_name": True}

    def model_post_init(self, __context: Any) -> None:
        """Apply governance profile if not custom."""
        if self.governance_profile != "custom":
            self._apply_governance_profile(self.governance_profile)

    def _apply_governance_profile(self, profile: GovernanceProfile) -> None:
        """Apply governance profile to physical configuration."""
        if profile in self.governance_profiles:
            gov_config = self.governance_profiles[profile]
            self.physical.validation.profile = gov_config.physical.validation_profile
            self.physical.modeling.mode = gov_config.physical.modeling_mode
            self.physical.validation._apply_profile(gov_config.physical.validation_profile)
            return

        # Fallback to hardcoded defaults
        if profile == "legacy-additive":
            self.physical.validation.profile = "legacy"
            self.physical.modeling.mode = "additive"
            self.physical.validation._apply_profile("legacy")
        elif profile == "legacy-rebuild":
            self.physical.validation.profile = "legacy"
            self.physical.modeling.mode = "rebuild"
            self.physical.validation._apply_profile("legacy")
        elif profile == "deep-additive":
            self.physical.validation.profile = "deep"
            self.physical.modeling.mode = "additive"
            self.physical.validation._apply_profile("deep")
        elif profile == "deep-rebuild":
            self.physical.validation.profile = "deep"
            self.physical.modeling.mode = "rebuild"
            self.physical.validation._apply_profile("deep")

    @classmethod
    def load(cls, config_path: Path | None = None) -> "NeatConfig":
        """Load configuration from file or use defaults."""
        try:
            import tomllib as tomli  # Python 3.11+
        except ImportError:
            import tomli  # type: ignore

        if config_path and config_path.exists():
            with config_path.open("rb") as f:
                data = tomli.load(f)
                if "tool" in data and "neat" in data["tool"]:
                    return cls(**data["tool"]["neat"])
                return cls(**data)

        # Try to find configuration files in current directory
        cwd = Path.cwd()
        for filename in ["neat.toml", "pyproject.toml"]:
            config_file = cwd / filename
            if config_file.exists():
                with config_file.open("rb") as f:
                    data = tomli.load(f)
                    if "tool" in data and "neat" in data["tool"]:
                        return cls(**data["tool"]["neat"])

        # Return default configuration
        return cls()

    def __str__(self) -> str:
        """Human-readable configuration summary."""
        lines = [
            f"Governance Profile: {self.governance_profile}",
            "",
            "Physical Data Model:",
            f"  Modeling Mode: {self.physical.modeling.mode}",
            f"  {self.physical.validation}".replace("\n", "\n  "),
        ]
        return "\n".join(lines)
