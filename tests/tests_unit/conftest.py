import os
import shutil
import tempfile
from pathlib import Path

import pytest
from rdflib import RDF, Literal, Namespace

from cognite.neat.graph import extractor, loader
from cognite.neat.graph.stores import MemoryStore
from cognite.neat.graph.transformation.transformer import domain2app_knowledge_graph
from cognite.neat.rules import importer
from cognite.neat.rules.exporter._rules2triples import get_instances_as_triples
from cognite.neat.rules.models.rules import Rules
from tests import config as config

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
def nordic44_inferred_rules() -> Rules:
    return importer.ExcelImporter(config.NORDIC44_INFERRED_RULES).to_rules()


@pytest.fixture(scope="session")
def transformation_rules() -> Rules:
    return importer.ExcelImporter(config.TNT_TRANSFORMATION_RULES).to_rules()


@pytest.fixture(scope="session")
def dms_compliant_rules() -> Rules:
    return importer.ExcelImporter(config.TNT_TRANSFORMATION_RULES_DMS_COMPLIANT).to_rules()


@pytest.fixture(scope="session")
def simple_rules() -> Rules:
    return importer.ExcelImporter(config.SIMPLE_TRANSFORMATION_RULES).to_rules()


@pytest.fixture(scope="session")
def transformation_rules_date() -> Rules:
    return importer.ExcelImporter(config.SIMPLE_TRANSFORMATION_RULES_DATES).to_rules()


@pytest.fixture(scope="function")
def small_graph(simple_rules) -> MemoryStore:
    graph_store = MemoryStore(
        base_prefix=simple_rules.metadata.prefix,
        namespace=simple_rules.metadata.namespace,
        prefixes=simple_rules.prefixes,
    )
    graph_store.init_graph()

    for triple in get_instances_as_triples(simple_rules):
        graph_store.graph.add(triple)
    return graph_store


@pytest.fixture(scope="function")
def graph_with_numeric_ids(simple_rules) -> MemoryStore:
    graph_store = MemoryStore(
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


@pytest.fixture(scope="function")
def graph_with_date(transformation_rules_date) -> MemoryStore:
    graph_store = MemoryStore(
        base_prefix=transformation_rules_date.metadata.prefix,
        namespace=transformation_rules_date.metadata.namespace,
        prefixes=transformation_rules_date.prefixes,
    )
    graph_store.init_graph()

    namespace = transformation_rules_date.metadata.namespace
    graph_store.graph.add((namespace["1"], RDF.type, namespace["PriceAreaConnection"]))
    graph_store.graph.add((namespace["1"], namespace["name"], Literal("Price Area Connection 1")))
    graph_store.graph.add((namespace["1"], namespace["priceArea"], namespace["2"]))
    graph_store.graph.add((namespace["1"], namespace["priceArea"], namespace["3"]))
    graph_store.graph.add((namespace["1"], namespace["endDate"], Literal("2020-01-01")))
    return graph_store


@pytest.fixture(scope="session")
def source_knowledge_graph() -> MemoryStore:
    graph = MemoryStore(namespace=Namespace("http://purl.org/nordic44#"))
    graph.init_graph()
    graph.import_from_file(config.NORDIC44_KNOWLEDGE_GRAPH)
    return graph


@pytest.fixture(scope="session")
def source_knowledge_graph_dirty(transformation_rules) -> MemoryStore:
    graph = MemoryStore(namespace=Namespace("http://purl.org/nordic44#"))
    graph.init_graph()
    graph.import_from_file(config.NORDIC44_KNOWLEDGE_GRAPH_DIRTY)
    for triple in get_instances_as_triples(transformation_rules):
        graph.graph.add(triple)
    return graph


@pytest.fixture(scope="session")
def solution_knowledge_graph_dirty(source_knowledge_graph_dirty, transformation_rules):
    return domain2app_knowledge_graph(source_knowledge_graph_dirty, transformation_rules)


@pytest.fixture(scope="session")
def solution_knowledge_graph(source_knowledge_graph, transformation_rules):
    return domain2app_knowledge_graph(source_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def mock_knowledge_graph(transformation_rules) -> MemoryStore:
    mock_graph = MemoryStore(prefixes=transformation_rules.prefixes, namespace=transformation_rules.metadata.namespace)
    mock_graph.init_graph(base_prefix=transformation_rules.metadata.prefix)

    class_count = {
        "RootCIMNode": 1,
        "GeographicalRegion": 1,
        "SubGeographicalRegion": 1,
        "Substation": 1,
        "Terminal": 2,
    }

    mock_triples = extractor.MockGraphGenerator(transformation_rules, class_count).extract()
    mock_graph.add_triples(mock_triples, batch_size=20000)

    return mock_graph


@pytest.fixture(scope="function")
def mock_rdf_assets(mock_knowledge_graph, transformation_rules):
    return loader.rdf2assets(mock_knowledge_graph, transformation_rules, data_set_id=123456)


@pytest.fixture(scope="function")
def mock_cdf_assets(mock_knowledge_graph, transformation_rules):
    return loader.rdf2assets(mock_knowledge_graph, transformation_rules, data_set_id=123456)


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
