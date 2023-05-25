import pandas as pd
import pytest
from openpyxl import load_workbook
from rdflib import Namespace

from cognite.neat.core import extractors, loader, parser
from cognite.neat.core.data_classes import TransformationRules
from cognite.neat.core.loader.graph_store import NeatGraphStore
from cognite.neat.core.mocks.graph import add_triples, generate_triples
from cognite.neat.core.transformer import domain2app_knowledge_graph
from tests import config


@pytest.fixture(scope="session")
def raw_transformation_tables() -> dict[str, pd.DataFrame]:
    return loader.rules.excel_file_to_table_by_name(config.TNT_TRANSFORMATION_RULES)


@pytest.fixture(scope="session")
def transformation_rules(raw_transformation_tables) -> TransformationRules:
    return parser.parse_transformation_rules(raw_transformation_tables)


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
    mock_graph = loader.NeatGraphStore(
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
    return extractors.rdf2assets(mock_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def mock_cdf_assets(mock_knowledge_graph, transformation_rules):
    return extractors.rdf2assets(mock_knowledge_graph, transformation_rules)


@pytest.fixture(scope="function")
def simple_rules():
    return parser.parse_transformation_rules(
        loader.rules.excel_file_to_table_by_name(config.SIMPLE_TRANSFORMATION_RULES)
    )


@pytest.fixture(scope="function")
def graph_capturing_sheet():
    return load_workbook(config.GRAPH_CAPTURING_SHEET)


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
