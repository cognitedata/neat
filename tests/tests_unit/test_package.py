import re
import sys

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
    docker_version = _extract_version_from_file(
        "Makefile",
        r'version="(\d+\.\d+\.\d+)"',
        "Failed to obtain docker version",
    )
    assert neat.__version__ == changelog_version == pyproject_toml == docker_version, "Inconsistent version variables"


def test_no_spaces_in_sub_folders() -> None:
    name_by_location = {path: path.name for path in (ROOT / "cognite").rglob("*") if path.is_dir() and " " in path.name}

    assert not name_by_location, f"Subfolders with spaces found: {name_by_location}"
