from pathlib import Path

from cognite import neat

PACKAGE_DIRECTORY = Path(neat.__file__).parent
EXAMPLES_DIRECTORY = PACKAGE_DIRECTORY / "workflows" / "examples"
EXAMPLE_RULES = EXAMPLES_DIRECTORY / "rules"
EXAMPLE_SOURCE_GRAPHS = EXAMPLES_DIRECTORY / "source-graphs"
EXAMPLE_WORKFLOWS = EXAMPLES_DIRECTORY / "workflows"
EXAMPLE_GRAPH_CAPTURING = EXAMPLES_DIRECTORY / "graph-sheets"
EXAMPLE_ONTOLOGIES = EXAMPLES_DIRECTORY / "ontologies"

TNT_TRANSFORMATION_RULES = EXAMPLE_RULES / "Rules-Nordic44-to-TNT.xlsx"
SIMPLE_TRANSFORMATION_RULES = EXAMPLE_RULES / "sheet2cdf-transformation-rules.xlsx"
NORDIC44_KNOWLEDGE_GRAPH = EXAMPLE_SOURCE_GRAPHS / "Knowledge-Graph-Nordic44.xml"
GRAPH_CAPTURING_SHEET = EXAMPLE_GRAPH_CAPTURING / "sheet2cdf-graph-capturing.xlsx"
WIND_ONTOLOGY = EXAMPLE_ONTOLOGIES / "wind-energy.owl"
UI_PATH = PACKAGE_DIRECTORY / "app" / "ui" / "neat-app" / "build"
