from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cognite.neat._exceptions import FileReadException

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli  # type: ignore

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_CDF_HINT_KEYS = ("default_config_yaml", "default_env", "default_organization_dir")


@dataclass(frozen=True)
class ToolkitProjectContext:
    """Resolved Toolkit project config, loaded once per directory import."""

    project_root: Path | None
    hints: dict[str, str] = field(default_factory=dict)
    config_paths: tuple[Path, ...] = ()
    merged_variables: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        data_model_dir: Path,
        *,
        toolkit_env: str | None = None,
        toolkit_config: Path | str | None = None,
    ) -> ToolkitProjectContext:
        project_root = find_toolkit_project_root(data_model_dir)
        if project_root is None:
            return cls(project_root=None)

        hints = parse_cdf_toml_hints(project_root)
        config_paths = resolve_toolkit_config_paths(
            project_root,
            hints=hints,
            toolkit_env=toolkit_env,
            toolkit_config=toolkit_config,
        )
        if not config_paths and toolkit_config is not None:
            config_paths = [Path(toolkit_config)]

        merged_variables: dict[str, Any] = {}
        for config_path in config_paths:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            variable_source = raw.get("variables") or {}
            if isinstance(variable_source, dict):
                merged_variables = deep_merge_dict(merged_variables, variable_source)

        return cls(
            project_root=project_root,
            hints=hints,
            config_paths=tuple(config_paths),
            merged_variables=merged_variables,
        )

    def variables_for(self, data_model_dir: Path, toolkit_version: str | None = None) -> dict[str, str]:
        if self.project_root is None:
            return apply_version_overrides({}, toolkit_version)
        module_path = module_path_under_toolkit(data_model_dir, self.project_root, self.hints)
        flat = flatten_variables_for_module(self.merged_variables, module_path)
        return apply_version_overrides(flat, toolkit_version)


def _path_under_toolkit_modules(start: Path, project_root: Path, hints: dict[str, str] | None = None) -> bool:
    """Return True when *start* sits under a Toolkit ``modules/`` tree for *project_root*."""
    try:
        relative = start.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False

    parts = relative.parts
    if parts and parts[0] == "modules":
        return True

    org_dir = (hints if hints is not None else parse_cdf_toml_hints(project_root)).get("default_organization_dir")
    return bool(org_dir and len(parts) > 1 and parts[0] == org_dir and parts[1] == "modules")


def find_toolkit_project_root(start: Path) -> Path | None:
    """Find the nearest Toolkit project root by walking up from *start*."""
    current = Path(start)
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / "default.config.yaml").exists():
            return candidate
        if (candidate / "cdf.toml").exists() and _path_under_toolkit_modules(current, candidate):
            return candidate
    return None


def parse_cdf_toml_hints(start_dir: Path) -> dict[str, str]:
    """Read Toolkit project hints from the nearest ``cdf.toml`` upward."""
    for ancestor in [Path(start_dir), *list(Path(start_dir).parents)[:8]]:
        cdf_toml = ancestor / "cdf.toml"
        if not cdf_toml.exists():
            continue
        try:
            with cdf_toml.open("rb") as file_handle:
                data = tomli.load(file_handle)
        except Exception:
            return {}
        cdf = data.get("cdf", {}) or {}
        hints: dict[str, str] = {}
        for key in _CDF_HINT_KEYS:
            value = cdf.get(key) or cdf.get(key.replace("_", "-"))
            if value:
                hints[key] = str(value)
        return hints
    return {}


def toolkit_config_search_roots(project_root: Path, hints: dict[str, str] | None = None) -> list[Path]:
    """Return Toolkit config directories, preferring the organization directory from ``cdf.toml``."""
    org_dir = (hints if hints is not None else parse_cdf_toml_hints(project_root)).get("default_organization_dir")
    if org_dir:
        org_root = project_root / org_dir
        if org_root.is_dir():
            return [org_root, project_root]
    return [project_root]


def resolve_toolkit_config_paths(
    project_root: Path,
    *,
    hints: dict[str, str] | None = None,
    toolkit_env: str | None = None,
    toolkit_config: Path | str | None = None,
) -> list[Path]:
    """Resolve the ordered Toolkit config chain: base + environment overlay."""
    if toolkit_config is not None:
        toolkit_config = Path(toolkit_config)
    hints = hints if hints is not None else parse_cdf_toml_hints(project_root)
    paths: list[Path] = []
    search_roots = toolkit_config_search_roots(project_root, hints)

    for root in search_roots:
        default_config = root / "default.config.yaml"
        if default_config.exists():
            paths.append(default_config)
            break

    env = toolkit_env
    if env is None:
        for root in search_roots:
            if (root / "config.dev.yaml").exists():
                env = "dev"
                break
    if env is None and hints.get("default_env"):
        env = hints["default_env"]

    overlay = toolkit_config
    if overlay is None and env:
        for root in search_roots:
            candidate = root / f"config.{env}.yaml"
            if candidate.exists():
                overlay = candidate
                break
    if overlay is None and hints.get("default_config_yaml"):
        for root in search_roots:
            candidate = root / hints["default_config_yaml"]
            if candidate.exists():
                overlay = candidate
                break

    if overlay is not None:
        overlay = Path(overlay)
        if overlay.exists() and overlay.resolve() not in {path.resolve() for path in paths}:
            paths.append(overlay)
    return paths


def deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (override wins on conflicts)."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def module_path_under_toolkit(
    data_model_dir: Path,
    project_root: Path,
    hints: dict[str, str] | None = None,
) -> Path | None:
    """Return the path under ``modules/`` for module-scoped variable resolution."""
    try:
        relative = data_model_dir.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None

    parts = list(relative.parts)
    org_dir = (hints if hints is not None else parse_cdf_toml_hints(project_root)).get("default_organization_dir")
    if org_dir and parts and parts[0] == org_dir:
        parts = parts[1:]

    if not parts or parts[0] != "modules":
        return None
    return Path(*parts[1:])


def _collect_scalar_variables(node: dict[str, Any], flat: dict[str, str]) -> None:
    """Collect scalar Toolkit variables from a config node, skipping nested module dicts."""
    for key, value in node.items():
        if key == "modules" or isinstance(value, dict | list):
            continue
        if value is not None:
            flat[str(key)] = str(value)


def flatten_variables_for_module(variables_root: dict[str, Any], module_path: Path | None) -> dict[str, str]:
    """Flatten Toolkit variables, applying module-specific overrides when available."""
    flat: dict[str, str] = {}
    _collect_scalar_variables(variables_root, flat)

    modules = variables_root.get("modules")
    if not isinstance(modules, dict):
        return flat

    # Toolkit stores project-wide variables directly under ``variables.modules``,
    # alongside per-module nested dicts (e.g. ``variables.modules.pidm``).
    _collect_scalar_variables(modules, flat)

    if module_path is None:
        return flat

    node: dict[str, Any] = modules
    for part in module_path.parts:
        child = node.get(part)
        if not isinstance(child, dict):
            break
        node = child
        _collect_scalar_variables(node, flat)
    return flat


def apply_version_overrides(variables: dict[str, str], toolkit_version: str | None) -> dict[str, str]:
    """Ensure ``version`` and ``viewVersion`` are available for template substitution."""
    result = dict(variables)
    resolved_version = toolkit_version or result.get("viewVersion") or result.get("version")
    if resolved_version is None:
        return result
    if toolkit_version is not None:
        result["version"] = toolkit_version
        result["viewVersion"] = toolkit_version
    else:
        result.setdefault("version", resolved_version)
        result.setdefault("viewVersion", resolved_version)
    return result


def load_toolkit_variables(
    data_model_dir: Path,
    *,
    toolkit_env: str | None = None,
    toolkit_config: Path | str | None = None,
    toolkit_version: str | None = None,
) -> dict[str, str]:
    """Load and flatten Toolkit template variables for a data model directory."""
    return ToolkitProjectContext.load(
        data_model_dir,
        toolkit_env=toolkit_env,
        toolkit_config=toolkit_config,
    ).variables_for(data_model_dir, toolkit_version)


def substitute_toolkit_variables(content: str, variables: dict[str, str], *, source: str) -> str:
    """Replace ``{{ variable }}`` placeholders in Toolkit YAML source text."""
    if "{{" not in content:
        return content

    def replace_match(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            available = ", ".join(sorted(variables)) if variables else "none"
            raise FileReadException(
                source,
                f"Unresolved toolkit variable '{{{{ {name} }}}}'. "
                f"Available variables: {available}. "
                "Ensure Toolkit config files (for example default.config.yaml or config.<env>.yaml "
                "referenced from cdf.toml) are present, "
                "or pass toolkit_env / toolkit_config to read.yaml().",
            )
        return variables[name]

    return _PLACEHOLDER_PATTERN.sub(replace_match, content)


def prepare_toolkit_yaml_content(
    content: str,
    *,
    source: Path,
    data_model_dir: Path | None = None,
    variables: dict[str, str] | None = None,
    toolkit_env: str | None = None,
    toolkit_config: Path | str | None = None,
    toolkit_version: str | None = None,
    enabled: bool = True,
) -> str:
    """Substitute Toolkit template variables in YAML source before parsing."""
    if not enabled or "{{" not in content:
        return content

    if variables is None:
        variables = load_toolkit_variables(
            data_model_dir or source.parent,
            toolkit_env=toolkit_env,
            toolkit_config=toolkit_config,
            toolkit_version=toolkit_version,
        )
    return substitute_toolkit_variables(content, variables, source=str(source))
