from pathlib import Path

TEST_FOLDER = Path(__file__).resolve().parent
ROOT = TEST_FOLDER.parent
PACKAGE_DIRECTORY = ROOT / "cognite" / "neat"

DOC_FOLDER = ROOT / "docs"
DOC_RULES = DOC_FOLDER / "artifacts" / "rules"
DATA_FOLDER = TEST_FOLDER / "data"
PYPROJECT_TOML = ROOT / "pyproject.toml"

# Example rule files
NORDIC44_INFERRED_RULES = TEST_FOLDER / "data" / "nordic44_inferred.xlsx"
SIMPLECIM_TRANSFORMATION_RULES = PACKAGE_DIRECTORY / "legacy" / "rules" / "examples" / "Rules-Nordic44.xlsx"
SIMPLECIM_TRANSFORMATION_RULES_DMS_COMPLIANT = (
    PACKAGE_DIRECTORY / "legacy" / "rules" / "examples" / "Rules-Nordic44-to-graphql.xlsx"
)
SIMPLE_TRANSFORMATION_RULES = (
    PACKAGE_DIRECTORY / "legacy" / "rules" / "examples" / "sheet2cdf-transformation-rules.xlsx"
)
SIMPLE_TRANSFORMATION_RULES_DATES = TEST_FOLDER / "data" / "sheet2cdf-transformation-rules-date.xlsx"
PARTIAL_MODEL_TEST_DATA = TEST_FOLDER / "data" / "partial-model"

# Example graph files
NORDIC44_KNOWLEDGE_GRAPH = PACKAGE_DIRECTORY / "graph" / "examples" / "Knowledge-Graph-Nordic44.xml"
NORDIC44_KNOWLEDGE_GRAPH_DIRTY = PACKAGE_DIRECTORY / "graph" / "examples" / "Knowledge-Graph-Nordic44-dirty.xml"

GRAPH_CAPTURING_SHEET = DATA_FOLDER / "sheet2cdf-graph-capturing.xlsx"
WIND_ONTOLOGY = DATA_FOLDER / "wind-energy.owl"
DEXPI_EXAMPLE = DATA_FOLDER / "depxi_example.xml"

CLASSIC_CDF_EXTRACTOR_DATA = DATA_FOLDER / "class_cdf_extractor_data"
