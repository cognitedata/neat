from pathlib import Path

TEST_FOLDER = Path(__file__).resolve().parent
ROOT = TEST_FOLDER.parent
PACKAGE_DIRECTORY = ROOT / "cognite" / "neat"

DOC_FOLDER = ROOT / "docs"
DOC_TUTORIAL = DOC_FOLDER / "tutorial"
DOC_KNOWLEDGE_ACQUISITION_TUTORIAL = DOC_TUTORIAL / "use-cases" / "spreadsheets"
DATA_FOLDER = TEST_FOLDER / "data"
PYPROJECT_TOML = ROOT / "pyproject.toml"

# Example rule files
NORDIC44_INFERRED_RULES = TEST_FOLDER / "data" / "nordic44_inferred.xlsx"
TNT_TRANSFORMATION_RULES = PACKAGE_DIRECTORY / "rules" / "examples" / "Rules-Nordic44-to-TNT.xlsx"
TNT_TRANSFORMATION_RULES_DMS_COMPLIANT = PACKAGE_DIRECTORY / "rules" / "examples" / "Rules-Nordic44-to-graphql.xlsx"
SIMPLE_TRANSFORMATION_RULES = PACKAGE_DIRECTORY / "rules" / "examples" / "sheet2cdf-transformation-rules.xlsx"
SIMPLE_TRANSFORMATION_RULES_DATES = TEST_FOLDER / "data" / "sheet2cdf-transformation-rules-date.xlsx"

# Example graph files
NORDIC44_KNOWLEDGE_GRAPH = PACKAGE_DIRECTORY / "graph" / "examples" / "Knowledge-Graph-Nordic44.xml"
NORDIC44_KNOWLEDGE_GRAPH_DIRTY = PACKAGE_DIRECTORY / "graph" / "examples" / "Knowledge-Graph-Nordic44-dirty.xml"

GRAPH_CAPTURING_SHEET = DATA_FOLDER / "sheet2cdf-graph-capturing.xlsx"
WIND_ONTOLOGY = DATA_FOLDER / "wind-energy.owl"
DEXPI_EXAMPLE = DATA_FOLDER / "depxi_example.xml"
