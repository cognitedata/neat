from pathlib import Path

from cognite.neat import constants

ROOT = Path(__file__).resolve().parent.parent

DATA_FOLDER = ROOT / "data"
PYPROJECT_TOML = ROOT / "pyproject.toml"

# Test use in-memory triple store
TNT_TRANSFORMATION_RULES = constants.TNT_TRANSFORMATION_RULES
SIMPLE_TRANSFORMATION_RULES = constants.SIMPLE_TRANSFORMATION_RULES
NORDIC44_KNOWLEDGE_GRAPH = constants.NORDIC44_KNOWLEDGE_GRAPH
