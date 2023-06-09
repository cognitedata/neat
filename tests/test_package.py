import re
import tomllib

from cognite import neat
from tests.config import PYPROJECT_TOML, ROOT


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
