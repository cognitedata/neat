"""Toolkit template-variable resolution for NEAT YAML imports.

NEAT cannot hard-depend on ``cognite-toolkit``, but Toolkit module YAML uses
``{{ variable }}`` placeholders. This module reimplements the subset of Toolkit
config resolution needed so ``format="toolkit"`` reads work without running
``cdf build``.

Strategy (pipeline)
-------------------
1. **Locate project** — Walk up from the data-model directory to find a Toolkit
   project root (``default.config.yaml`` and/or ``cdf.toml`` above a ``modules/``
   tree). Guard against unrelated repo-root ``cdf.toml`` files that are not
   Toolkit projects for the path being read.

2. **Resolve config chain** — Merge configs in Toolkit order:
   ``default.config.yaml`` (project and/or module-local), then an environment overlay.
   Overlay selection: explicit ``toolkit_config``, then ``config.<toolkit_env>.yaml``,
   then ``cdf.toml`` ``default_config_yaml`` / ``default_env`` (e.g. sandbox),
   then ``config.dev.yaml`` / ``config.sandbox.yaml``.
   Prefer the organization directory from ``cdf.toml`` when present
   (e.g. ``beyond-the-plant/config.dev.yaml``).

3. **Flatten variables** — Build a flat ``name -> value`` map from the merged
   ``variables:`` tree. Collect scalars at the root, at ``variables.modules``
   (project-wide globals — common in ADA20/BTP-style configs), then walk the
   module path for nested overrides (later wins).

4. **Version aliases** — Ensure both ``version`` and ``viewVersion`` exist
   (Toolkit YAML uses either). Explicit ``toolkit_version`` overrides both.

5. **Substitute** — Replace ``{{ name }}`` in YAML text *before* parsing.
   Unresolved names raise ``FileReadException`` with available variables listed.

Performance note
----------------
Load config once per directory import via :class:`ToolkitProjectContext`, then
reuse the flattened map for every YAML file under that directory.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cognite.neat._data_model.models.dms import RequestSchema, SpaceRequest
from cognite.neat._exceptions import FileReadException

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli  # type: ignore

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_CDF_HINT_KEYS = ("default_config_yaml", "default_env", "default_organization_dir")

# Shared Args snippet for session ``read.yaml`` docstrings (keep public kwargs as three fields).
TOOLKIT_READ_ARGS_DOC = """\
        toolkit_env (str | None): Toolkit environment name (e.g. ``dev``) for config overlay resolution.
        toolkit_config (str | Path | None): Explicit Toolkit config YAML to merge on top of ``default.config.yaml``.
        toolkit_version (str | None): Override ``version`` / ``viewVersion`` template variables."""


@dataclass(frozen=True)
class ToolkitReadOptions:
    """Caller options for Toolkit template variable resolution.

    Public session APIs expose ``toolkit_env`` / ``toolkit_config`` / ``toolkit_version``;
    pack them once with :meth:`from_args` and thread this object through importers.
    """

    env: str | None = None
    config: Path | None = None
    version: str | None = None
    substitute: bool = True

    @classmethod
    def from_args(
        cls,
        toolkit_env: str | None = None,
        toolkit_config: Path | str | None = None,
        toolkit_version: str | None = None,
        *,
        substitute_toolkit_variables: bool = True,
    ) -> ToolkitReadOptions:
        return cls(
            env=toolkit_env,
            config=Path(toolkit_config) if toolkit_config is not None else None,
            version=toolkit_version,
            substitute=substitute_toolkit_variables,
        )


@dataclass(frozen=True)
class ToolkitProjectContext:
    """Resolved Toolkit project config, loaded once per directory import.

    Holds the merged ``variables:`` tree (still nested). Call :meth:`variables_for`
    to flatten for a specific module path and apply version overrides.
    """

    project_root: Path | None
    hints: dict[str, str] = field(default_factory=dict)
    config_paths: tuple[Path, ...] = ()
    merged_variables: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, data_model_dir: Path, options: ToolkitReadOptions | None = None) -> ToolkitProjectContext:
        options = options or ToolkitReadOptions()
        project_root = find_toolkit_project_root(data_model_dir)
        if project_root is None:
            return cls(project_root=None)

        hints = parse_cdf_toml_hints(project_root)
        config_paths = resolve_toolkit_config_paths(project_root, hints=hints, options=options)
        if not config_paths and options.config is not None:
            config_paths = [options.config]
        module_default = find_module_default_config(data_model_dir, project_root)
        if module_default is not None:
            already = {path.resolve() for path in config_paths}
            if module_default.resolve() not in already:
                project_default = (project_root / "default.config.yaml").resolve()
                insert_at = 1 if config_paths and config_paths[0].resolve() == project_default else 0
                config_paths = [*config_paths[:insert_at], module_default, *config_paths[insert_at:]]

        # Deep-merge in chain order so env overlays win over default.config.yaml.
        merged_variables: dict[str, Any] = {}
        for config_path in config_paths:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            variable_source = variables_mapping_from_config(raw)
            if variable_source:
                merged_variables = deep_merge_dict(merged_variables, variable_source)

        return cls(
            project_root=project_root,
            hints=hints,
            config_paths=tuple(config_paths),
            merged_variables=merged_variables,
        )

    def variables_for(self, data_model_dir: Path, version: str | None = None) -> dict[str, str]:
        if self.project_root is None:
            return apply_version_overrides({}, version)
        module_path = module_path_under_toolkit(data_model_dir, self.project_root, self.hints)
        flat = flatten_variables_for_module(self.merged_variables, module_path)
        return apply_version_overrides(flat, version)


# ---------------------------------------------------------------------------
# Project / config discovery
# ---------------------------------------------------------------------------


def _organization_dir(hints: dict[str, str] | None, project_root: Path | None = None) -> str | None:
    if hints is None and project_root is not None:
        hints = parse_cdf_toml_hints(project_root)
    return (hints or {}).get("default_organization_dir")


def _first_existing(roots: list[Path], relative: str) -> Path | None:
    for root in roots:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def _path_under_toolkit_modules(start: Path, project_root: Path, hints: dict[str, str] | None = None) -> bool:
    """Return True when *start* sits under a Toolkit ``modules/`` tree for *project_root*.

    Used so a repo-root ``cdf.toml`` alone does not claim unrelated paths (e.g. test
    fixtures outside ``modules/``) as Toolkit projects.
    """
    try:
        relative = start.resolve().relative_to(project_root.resolve())
    except ValueError:
        return False

    parts = relative.parts
    if parts and parts[0] == "modules":
        return True

    org_dir = _organization_dir(hints, project_root)
    return bool(org_dir and len(parts) > 1 and parts[0] == org_dir and parts[1] == "modules")


def _is_filesystem_path(path: object) -> bool:
    """True for real pathlib objects (not unittest mocks with spec=Path)."""
    return type(path).__module__.startswith("pathlib")


def _as_directory(start: Path) -> Path | None:
    if not _is_filesystem_path(start):
        return None
    current = Path(start)
    return current.parent if current.is_file() else current


def _toolkit_root_markers(candidate: Path) -> tuple[bool, bool, bool]:
    return (
        (candidate / "modules").is_dir(),
        (candidate / "cdf.toml").exists(),
        (candidate / "default.config.yaml").exists(),
    )


def _is_toolkit_project_root_dir(candidate: Path) -> bool:
    has_modules, has_cdf, has_default = _toolkit_root_markers(candidate)
    return has_modules and (has_cdf or has_default)


def find_toolkit_project_root(start: Path) -> Path | None:
    """Find the nearest Toolkit project root by walking up from *start*.

    Prefer a ``cdf.toml`` that owns this path (under ``modules/``), then a
    ``default.config.yaml`` sitting next to ``modules/``. A *module-local*
    ``modules/<name>/default.config.yaml`` is only a fallback — it must not
    hide the real project root where ``config.sandbox.yaml`` / ``cdf.toml`` live.

    The start path itself counts as the root when it contains ``modules/`` plus
    ``cdf.toml`` or ``default.config.yaml``. If *start* is a parent folder of a
    single Toolkit project (one child with those markers), that child is used.
    """
    current = _as_directory(start)
    if current is None:
        return None
    fallback: Path | None = None
    for candidate in [current, *current.parents]:
        has_modules, has_cdf, has_default = _toolkit_root_markers(candidate)
        if has_cdf and (
            (candidate.resolve() == current.resolve() and has_modules)
            or _path_under_toolkit_modules(current, candidate)
        ):
            return candidate
        if has_default and has_modules:
            return candidate
        if fallback is None and has_default:
            fallback = candidate

    try:
        child_roots = [child for child in current.iterdir() if child.is_dir() and _is_toolkit_project_root_dir(child)]
    except OSError:
        child_roots = []
    if len(child_roots) == 1:
        return child_roots[0]
    return fallback


def find_module_default_config(start: Path, project_root: Path) -> Path | None:
    """Return a module-local ``default.config.yaml`` between *start* and *project_root*."""
    current = _as_directory(start)
    if current is None:
        return None
    project_root = project_root.resolve()
    for ancestor in [current, *current.parents]:
        resolved = ancestor.resolve()
        if resolved == project_root:
            break
        candidate = ancestor / "default.config.yaml"
        if candidate.exists():
            return candidate
        try:
            resolved.relative_to(project_root)
        except ValueError:
            break
    return None


def parse_cdf_toml_hints(start_dir: Path) -> dict[str, str]:
    """Read Toolkit project hints from the nearest ``cdf.toml`` upward.

    Only the ``[cdf]`` keys that affect config path / env selection are kept.
    """
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
    org_dir = _organization_dir(hints, project_root)
    if org_dir:
        org_root = project_root / org_dir
        if org_root.is_dir():
            return [org_root, project_root]
    return [project_root]


def resolve_toolkit_config_paths(
    project_root: Path,
    *,
    hints: dict[str, str] | None = None,
    options: ToolkitReadOptions | None = None,
) -> list[Path]:
    """Resolve the ordered Toolkit config chain: base + environment overlay.

    Selection order for the overlay when not passed explicitly:
    1. ``config.<toolkit_env>.yaml`` when ``toolkit_env`` is set
    2. ``default_config_yaml`` / ``default_env`` from ``cdf.toml`` (e.g. sandbox)
    3. ``config.dev.yaml`` then ``config.sandbox.yaml`` if present
    """
    options = options or ToolkitReadOptions()
    hints = hints if hints is not None else parse_cdf_toml_hints(project_root)
    search_roots = toolkit_config_search_roots(project_root, hints)

    paths: list[Path] = []
    if default_config := _first_existing(search_roots, "default.config.yaml"):
        paths.append(default_config)

    overlay = options.config
    if overlay is None and options.env:
        overlay = _first_existing(search_roots, f"config.{options.env}.yaml")
    if overlay is None and hints.get("default_config_yaml"):
        overlay = _first_existing(search_roots, hints["default_config_yaml"])
    if overlay is None and hints.get("default_env"):
        overlay = _first_existing(search_roots, f"config.{hints['default_env']}.yaml")
    if overlay is None:
        for heuristic in ("config.dev.yaml", "config.sandbox.yaml"):
            overlay = _first_existing(search_roots, heuristic)
            if overlay is not None:
                break

    if overlay is not None and overlay.exists() and overlay.resolve() not in {path.resolve() for path in paths}:
        paths.append(overlay)
    return paths


# ---------------------------------------------------------------------------
# Variable flattening and substitution
# ---------------------------------------------------------------------------


def variables_mapping_from_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return the ``variables:`` mapping, or a flat module ``default.config.yaml`` map."""
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("variables")
    if isinstance(nested, dict):
        return nested
    return {
        key: value
        for key, value in raw.items()
        if value is not None and not isinstance(value, dict | list) and not str(key).startswith("#")
    }


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
    """Return the path under ``modules/`` for module-scoped variable resolution.

    Example: ``modules/btp/data_modeling/dm`` → ``btp/data_modeling/dm``, used to
    walk ``variables.modules.btp...`` for nested overrides.
    """
    try:
        relative = data_model_dir.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None

    parts = list(relative.parts)
    org_dir = _organization_dir(hints, project_root)
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
    """Flatten Toolkit variables, applying module-specific overrides when available.

    Layering (later overwrites earlier):
    1. Scalars under ``variables:``
    2. Scalars under ``variables.modules:`` (project globals next to nested module dicts)
    3. Scalars along the module path under ``variables.modules.<...>``
    """
    flat: dict[str, str] = {}
    _collect_scalar_variables(variables_root, flat)

    modules = variables_root.get("modules")
    if not isinstance(modules, dict):
        return flat

    # Project-wide globals often live directly under variables.modules (ADA20/BTP).
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


def load_toolkit_variables(data_model_dir: Path, options: ToolkitReadOptions | None = None) -> dict[str, str]:
    """Load and flatten Toolkit template variables for a data model directory."""
    options = options or ToolkitReadOptions()
    return ToolkitProjectContext.load(data_model_dir, options).variables_for(data_model_dir, options.version)


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
    options: ToolkitReadOptions | None = None,
) -> str:
    """Substitute Toolkit template variables in YAML source before parsing.

    Prefer passing a precomputed *variables* map when reading many files in one
    directory so config is not reloaded per file.
    """
    options = options or ToolkitReadOptions()
    if not options.substitute or "{{" not in content:
        return content

    if variables is None:
        variables = load_toolkit_variables(data_model_dir or source.parent, options)
    return substitute_toolkit_variables(content, variables, source=str(source))


def populate_toolkit_governed_spaces(schema: RequestSchema) -> RequestSchema:
    """Mark all spaces present in a toolkit module import as NEAT-governed.

    Toolkit modules are multi-space by design (data model space plus domain spaces).
    Without this, NEAT only governs the data model space and falls back to CDF for
    views/containers in other spaces — which is surprising when reading local YAML.

    Explicit ``governedSpaces`` from NEAT Excel metadata is left unchanged.
    """
    if schema.extra.governed_spaces:
        return schema

    space_ids = {schema.data_model.space}
    space_ids.update(space.space for space in schema.spaces)
    space_ids.update(view.space for view in schema.views)
    space_ids.update(container.space for container in schema.containers)

    additional = sorted(space_ids - {schema.data_model.space})
    if not additional:
        return schema

    updated = schema.model_copy(deep=True)
    updated.extra.governed_spaces = [SpaceRequest(space=space_id) for space_id in additional]
    return updated
