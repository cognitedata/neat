import tomllib

from cognite import neat
from tests.config import PYPROJECT_TOML


def test_consistent_version_variables():
    pyproject = tomllib.loads(PYPROJECT_TOML.read_text())

    assert neat.__version__ == pyproject["tool"]["poetry"]["version"], "Inconsistent version variables"
