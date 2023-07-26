from pathlib import Path
from cognite import neat


PACKAGE_DIRECTORY = Path(neat.__file__).parent

UI_PATH = PACKAGE_DIRECTORY / "app" / "ui" / "neat-app" / "build"

EXAMPLE_RULES = PACKAGE_DIRECTORY / "rules" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "graph" / "examples"
EXAMPLE_WORKFLOWS = PACKAGE_DIRECTORY / "workflows" / "examples"
