import pytest
from rdflib import Namespace

from cognite.neat import rules
from cognite.neat.graph import loaders, extractors
from cognite.neat.stores.graph_store import NeatGraphStore
from cognite.neat.graph.extractors.mocks import generate_triples
from cognite.neat.rules.parser import RawTables, read_excel_file_to_table_by_name
from cognite.neat.rules.importer.ontology2excel import owl2excel
from cognite.neat.rules.models import TransformationRules
from cognite.neat.graph.transformations.transformer import domain2app_knowledge_graph
from cognite.neat.utils.utils import add_triples
from tests import config


@pytest.fixture(scope="session")
def transformation_rules() -> TransformationRules:
    return rules.parse_rules_from_excel_file(config.TNT_TRANSFORMATION_RULES)


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
    add_triples(mock_graph, mock_triples, batch_size=20000)

    return mock_graph


@pytest.fixture(scope="function")
def mock_rdf_assets(mock_knowledge_graph, transformation_rules):
    return loaders.rdf2assets(mock_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def mock_cdf_assets(mock_knowledge_graph, transformation_rules):
    return loaders.rdf2assets(mock_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def simple_rules():
    return rules.parse_rules_from_excel_file(config.SIMPLE_TRANSFORMATION_RULES)


@pytest.fixture(scope="function")
def graph_capturing_sheet():
    # return load_workbook(config.GRAPH_CAPTURING_SHEET)
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


@pytest.fixture(scope="function")
def owl_based_rules():
    owl2excel(config.WIND_ONTOLOGY)

    return RawTables(**read_excel_file_to_table_by_name(config.WIND_ONTOLOGY.parent / "transformation_rules.xlsx"))
