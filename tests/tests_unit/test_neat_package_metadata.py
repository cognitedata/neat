import re
import sys
from pathlib import Path

from cognite import neat
from tests.config import PYPROJECT_TOML, ROOT

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _extract_version_from_file(filename, search_pattern, error_message):
    changelog = (ROOT / filename).read_text()
    if not (changelog_version_result := re.search(search_pattern, changelog)):
        raise ValueError(error_message)
    return changelog_version_result.groups()[0]


def test_consistent_version_variables():
    pyproject = tomllib.loads(PYPROJECT_TOML.read_text())
    pyproject_toml = pyproject["tool"]["poetry"]["version"]

    changelog_version = _extract_version_from_file(
        "./docs/CHANGELOG.md",
        r"\[(\d+\.\d+\.\d+)\]",
        "Failed to obtain changelog version",
    )
    assert neat.__version__ == changelog_version == pyproject_toml, "Inconsistent version variables"


def test_no_spaces_in_sub_folders() -> None:
    name_by_location: dict[Path, str] = {}
    to_check = [ROOT / "cognite"]
    while to_check:
        current = to_check.pop()
        for path in current.iterdir():
            if path.is_dir():
                if path.name not in {"node_modules"}:
                    to_check.append(path)
                if " " in path.name:
                    name_by_location[path] = path.name
                    raise ValueError(f"Subfolder with spaces found: {path}")

    assert not name_by_location, f"Subfolders with spaces found: {name_by_location}"
