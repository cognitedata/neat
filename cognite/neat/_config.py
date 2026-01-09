import sys
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from cognite.neat._exceptions import UserInputError
from cognite.neat._issues import ConsistencyError, ModelSyntaxError
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.useful_types import ModusOperandi

if sys.version_info >= (3, 11):
    import tomllib as tomli  # Python 3.11+
else:
    import tomli  # type: ignore

# Public profiles
PredefinedProfile: TypeAlias = Literal["legacy-additive", "legacy-rebuild", "deep-additive", "deep-rebuild"]

# Private profiles only
_PrivateProfiles: TypeAlias = Literal["no-validation-additive", "no-validation-rebuild"]

# All profiles (union of public and private)
_AllProfiles: TypeAlias = PredefinedProfile | _PrivateProfiles


class ConfigModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)


class ValidationConfig(ConfigModel):
    """Validation configuration."""

    exclude: list[str] = Field(default_factory=list)
    override: bool = Field(False, description="If enabled, all validators are skipped.")

    def can_run_validator(self, code: str, issue_type: type) -> bool:
        """
        Check if a specific validator should run.

        Args:
            code: Validation code (e.g., "NEAT-DMS-CONTAINER-001")
            issue_type: Issue type (e.g., ModelSyntaxError, ConsistencyError, Recommendation)

        Returns:
            True if validator should run, False otherwise
        """

        is_excluded = self._is_excluded(code, self.exclude)

        if issue_type in [ModelSyntaxError, ConsistencyError] and is_excluded and not self.override:
            print(f"Validator {code} was excluded however it is a critical validator and will still run.")
            return True
        else:
            return not is_excluded

    @classmethod
    def _is_excluded(cls, code: str, patterns: list[str]) -> bool:
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


class ModelingConfig(ConfigModel):
    """Modeling configuration."""

    mode: ModusOperandi = "additive"


class AlphaFlagConfig(ConfigModel):
    """Alpha feature flags configuration."""

    fix_validation_issues: bool = Field(
        default=False,
        description="If enabled, Neat will attempt to automatically fix certain validation issues in the data model.",
    )
    enable_experimental_validators: bool = Field(
        default=False,
        description="If enabled, Neat will run experimental validators that are still in alpha stage.",
    )

    def __setattr__(self, key: str, value: Any) -> None:
        """Set attribute value or raise AttributeError."""
        if key in self.model_fields:
            super().__setattr__(key, value)
        else:
            available_flags = humanize_collection(type(self).model_fields.keys())
            raise UserInputError(f"Alpha flag '{key}' not found. Available flags: {available_flags}.")

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebooks."""
        lines = ["<b>Alpha Feature Flags:</b>"]
        for field_name, field in type(self).model_fields.items():
            value = getattr(self, field_name)
            display = "Enabled" if value else "Disabled"
            lines.append(f"<li><b>{field_name}</b>: {display} - {field.description}</li>")
        return "<ul>" + "\n".join(lines) + "</ul>"


class NeatConfig(ConfigModel):
    """NeatSession configuration."""

    profile: str
    validation: ValidationConfig
    modeling: ModelingConfig
    alpha: AlphaFlagConfig = Field(default_factory=AlphaFlagConfig)

    def __str__(self) -> str:
        """Human-readable configuration summary."""
        lines = [
            f"Profile: {self.profile}",
            f"Modeling Mode: {self.modeling.mode}",
            f"Validation: {self.validation}",
        ]
        return "\n".join(lines)

    @classmethod
    def create_predefined(cls, profile: PredefinedProfile = "legacy-additive") -> "NeatConfig":
        """Create NeatConfig from internal profiles.

        Args:
            profile: Profile name to use. Defaults to "legacy-additive".

        !!! note "Predefined Profiles"
            The following predefined profiles are available:

            - `legacy-additive`: Additive modeling with legacy validation rules.
            - `legacy-rebuild`: Rebuild modeling with legacy validation rules.
            - `deep-additive`: Additive modeling with deep validation rules.
            - `deep-rebuild`: Rebuild modeling with deep validation rules.
        """
        available_profiles = internal_profiles()
        if profile not in available_profiles:
            raise UserInputError(
                f"Profile {profile!r} not found. Available predefined profiles: "
                f"{humanize_collection(available_profiles.keys())}."
            )
        return available_profiles[profile]


def internal_profiles() -> dict[_AllProfiles, NeatConfig]:
    """Get internal NeatConfig profile by name."""
    return {
        "legacy-additive": NeatConfig(
            profile="legacy-additive",
            modeling=ModelingConfig(mode="additive"),
            validation=ValidationConfig(
                exclude=[
                    "NEAT-DMS-AI-READINESS-*",
                    "NEAT-DMS-CONNECTIONS-002",
                    "NEAT-DMS-CONNECTIONS-REVERSE-007",
                    "NEAT-DMS-CONNECTIONS-REVERSE-008",
                    "NEAT-DMS-CONSISTENCY-001",
                ]
            ),
        ),
        "legacy-rebuild": NeatConfig(
            profile="legacy-rebuild",
            modeling=ModelingConfig(mode="rebuild"),
            validation=ValidationConfig(
                exclude=[
                    "NEAT-DMS-AI-READINESS-*",
                    "NEAT-DMS-CONNECTIONS-002",
                    "NEAT-DMS-CONNECTIONS-REVERSE-007",
                    "NEAT-DMS-CONNECTIONS-REVERSE-008",
                    "NEAT-DMS-CONSISTENCY-001",
                ]
            ),
        ),
        "deep-additive": NeatConfig(
            profile="deep-additive",
            modeling=ModelingConfig(mode="additive"),
            validation=ValidationConfig(exclude=[]),
        ),
        "deep-rebuild": NeatConfig(
            profile="deep-rebuild",
            modeling=ModelingConfig(mode="rebuild"),
            validation=ValidationConfig(exclude=[]),
        ),
        "no-validation-rebuild": NeatConfig(
            profile="no-validation-rebuild",
            modeling=ModelingConfig(mode="rebuild"),
            validation=ValidationConfig(exclude=["*"], override=True),
        ),
        "no-validation-additive": NeatConfig(
            profile="no-validation-additive",
            modeling=ModelingConfig(mode="additive"),
            validation=ValidationConfig(exclude=["*"], override=True),
        ),
    }


def get_neat_config_from_file(config_file_name: str, profile: str) -> NeatConfig:
    """Get NeatConfig from file or internal profiles.

    Args:
        config_file_name: Path to configuration file.
        profile: Profile name to use.
    Returns:
        NeatConfig instance.
    """

    if not config_file_name.endswith(".toml"):
        raise ValueError("config_file_name must end with '.toml'")

    file_path = Path.cwd() / config_file_name

    if file_path.exists():
        with file_path.open("rb") as f:
            toml = tomli.load(f)

        if "tool" in toml and "neat" in toml["tool"]:
            data = toml["tool"]["neat"]
        elif "neat" in toml:
            data = toml["neat"]
        else:
            raise ValueError("No [tool.neat] or [neat] section found in the configuration file.")

        toml_profile = data.get("profile")
        toml_profiles = data.get("profiles")
        hardcoded_profiles = internal_profiles()

        if toml_profile and toml_profile in hardcoded_profiles:
            raise ValueError(f"Internal profile '{toml_profile}' cannot be used in external configuration file.")

        if toml_profiles and any(p in hardcoded_profiles for p in toml_profiles.keys()):
            raise ValueError(
                "Internal profiles cannot be redefined in external configuration file: "
                f"{set(hardcoded_profiles.keys()).intersection(toml_profiles.keys())}"
            )

        if toml_profile and profile == toml_profile:
            return NeatConfig(**data)
        elif (built_in_profiles := data.get("profiles")) and profile in built_in_profiles:
            return NeatConfig(profile=profile, **data["profiles"][profile])
        else:
            raise ValueError(f"Profile '{profile}' not found in configuration file.")
    else:
        raise FileNotFoundError(f"Configuration file '{file_path}' not found.")
