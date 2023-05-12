from pathlib import Path

from cognite import neat

PACKAGE_DIRECTORY = Path(neat.__file__).parent
EXAMPLES_DIRECTORY = PACKAGE_DIRECTORY / "examples"
EXAMPLE_RULES = EXAMPLES_DIRECTORY / "rules"
EXAMPLE_SOURCE_GRAPHS = EXAMPLES_DIRECTORY / "source_graphs"
EXAMPLE_WORKFLOWS = EXAMPLES_DIRECTORY / "workflows"

TNT_TRANSFORMATION_RULES = EXAMPLE_RULES / "Rules-Nordic44-to-TNT.xlsx"
SIMPLE_TRANSFORMATION_RULES = EXAMPLE_RULES / "sheet2cdf-transformation-rules.xlsx"
NORDIC44_KNOWLEDGE_GRAPH = EXAMPLE_SOURCE_GRAPHS / "Knowledge-Graph-Nordic44.xml"
UI_PATH = PACKAGE_DIRECTORY / "explorer-ui" / "neat-app" / "build"
