import os
import shutil
import tempfile
from pathlib import Path

import pytest
from rdflib import RDF, Literal, Namespace

from cognite.neat import rules
from cognite.neat.graph import extractors, loaders
from cognite.neat.graph.extractors.mocks import generate_triples
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformations.transformer import domain2app_knowledge_graph
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.rules.models import TransformationRules
from tests import config

# Setup config for Neat App
_TMP_DIR = Path(tempfile.gettempdir()) / "neat" / "data"
# Cleanup tmp dir
shutil.rmtree(_TMP_DIR, ignore_errors=True)
_TMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["NEAT_DATA_PATH"] = str(_TMP_DIR)
os.environ["NEAT_CDF_PROJECT"] = "get-power-grid"
os.environ["NEAT_CDF_CLIENT_ID"] = "uuid"
os.environ["NEAT_CDF_CLIENT_SECRET"] = "secret"
os.environ["NEAT_CDF_CLIENT_NAME"] = "neat-test-service"
os.environ["NEAT_CDF_BASE_URL"] = "https://bluefield.cognitedata.com"
os.environ["NEAT_CDF_TOKEN_URL"] = " https://login.microsoftonline.com/uuid4/oauth2/v2.0/token"
os.environ["NEAT_CDF_SCOPES"] = "https://bluefield.cognitedata.com/.default"
os.environ["NEAT_CDF_DEFAULT_DATASET_ID"] = "3931920688237191"
os.environ["NEAT_LOAD_EXAMPLES"] = "1"


@pytest.fixture(scope="session")
def transformation_rules() -> TransformationRules:
    return rules.parser.parse_rules_from_excel_file(config.TNT_TRANSFORMATION_RULES)


@pytest.fixture(scope="session")
def simple_rules() -> TransformationRules:
    return rules.parser.parse_rules_from_excel_file(config.SIMPLE_TRANSFORMATION_RULES)


@pytest.fixture(scope="function")
def small_graph(simple_rules) -> NeatGraphStore:
    graph_store = NeatGraphStore(
        base_prefix=simple_rules.metadata.prefix,
        namespace=simple_rules.metadata.namespace,
        prefixes=simple_rules.prefixes,
    )
    graph_store.init_graph()

    for triple in get_instances_as_triples(simple_rules):
        graph_store.graph.add(triple)
    return graph_store


@pytest.fixture(scope="function")
def graph_with_numeric_ids(simple_rules) -> NeatGraphStore:
    graph_store = NeatGraphStore(
        base_prefix=simple_rules.metadata.prefix,
        namespace=simple_rules.metadata.namespace,
        prefixes=simple_rules.prefixes,
    )
    graph_store.init_graph()

    namespace = simple_rules.metadata.namespace
    graph_store.graph.add((namespace["1"], RDF.type, namespace["PriceAreaConnection"]))
    graph_store.graph.add((namespace["1"], namespace["name"], Literal("Price Area Connection 1")))
    graph_store.graph.add((namespace["1"], namespace["priceArea"], namespace["2"]))
    graph_store.graph.add((namespace["1"], namespace["priceArea"], namespace["3"]))
    return graph_store


@pytest.fixture(scope="session")
def source_knowledge_graph():
    graph = NeatGraphStore(namespace=Namespace("http://purl.org/nordic44#"))
    graph.init_graph()
    graph.import_from_file(config.NORDIC44_KNOWLEDGE_GRAPH)
    return graph


@pytest.fixture(scope="session")
def solution_knowledge_graph(source_knowledge_graph, transformation_rules):
    return domain2app_knowledge_graph(source_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def mock_knowledge_graph(transformation_rules):
    mock_graph = NeatGraphStore(
        prefixes=transformation_rules.prefixes, namespace=transformation_rules.metadata.namespace
    )
    mock_graph.init_graph(base_prefix=transformation_rules.metadata.prefix)

    class_count = {
        "RootCIMNode": 1,
        "GeographicalRegion": 1,
        "SubGeographicalRegion": 1,
        "Substation": 1,
        "Terminal": 2,
    }

    mock_triples = generate_triples(transformation_rules, class_count)
    mock_graph.add_triples(mock_triples, batch_size=20000)

    return mock_graph


@pytest.fixture(scope="function")
def mock_rdf_assets(mock_knowledge_graph, transformation_rules):
    return loaders.rdf2assets(mock_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def mock_cdf_assets(mock_knowledge_graph, transformation_rules):
    return loaders.rdf2assets(mock_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def graph_capturing_sheet():
    return extractors.read_graph_excel_file_to_table_by_name(config.GRAPH_CAPTURING_SHEET)


@pytest.fixture(scope="function")
def grid_graphql_schema():
    return """type CountryGroup {
  name: String!
}

type Country {
  name: String!
  countryGroup: CountryGroup
  TSO: [String!]!
}

type PriceArea {
  name: String!
  country: Country
  priceAreaConnection: [PriceAreaConnection]
}

type PriceAreaConnection {
  name: String!
  priceArea: [PriceArea]
}"""
