import pandas as pd
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph, Namespace

from cognite.neat.core.data_classes import TransformationRules
from cognite.neat.core.data_classes.rules import RuleType
from cognite.neat.core.transformer import domain2app_knowledge_graph


def test_domain2app_knowledge_graph(transformation_rules: TransformationRules, source_knowledge_graph: Graph):
    # Arrange
    rules = transformation_rules
    domain_graph = source_knowledge_graph

    # Act
    app_graph = domain2app_knowledge_graph(domain_graph, rules)

    # Assert
    res = app_graph.query(
        """SELECT ?o WHERE {<http://purl.org/nordic44#_f17695aa-9aeb-11e5-91da-b8763fd99c5f> rdf:type ?o}"""
    )
    assert list(res)[0][0] == Namespace("http://purl.org/cognite/tnt#").Substation


def test_domain2app_knowledge_graph_raw_lookup(
    transformation_rules: TransformationRules, source_knowledge_graph: Graph
):
    # Arrange
    rules = transformation_rules.copy(deep=True)
    rules.properties["row 18"].rule += " | TerminalName(NordicName, TNTName)"
    rules.properties["row 18"].rule_type = RuleType.rawlookup
    domain_graph = source_knowledge_graph
    database_name = "look_up"

    # Act
    with monkeypatch_cognite_client() as client_mock:

        def mock_retrieve(db_name, table_name, **_):
            if db_name == database_name and table_name == "TerminalName":
                return pd.DataFrame([{"NordicName": "ARENDAL 300 A T1", "TNTName": "Gjerstad"}])

        client_mock.raw.rows.retrieve_dataframe = mock_retrieve
        app_graph = domain2app_knowledge_graph(
            domain_graph, rules, client=client_mock, cdf_lookup_database=database_name
        )

    Gjerstad_node = app_graph.query(
        "SELECT ?o WHERE {<http://purl.org/nordic44#_2dd9019e-bdfb-11e5-94fa-c8f73332c8f4> tnt:IdentifiedObject.name ?o}"
    )

    NaN_node = app_graph.query(
        "SELECT ?o WHERE {<http://purl.org/nordic44#_2dd9040e-bdfb-11e5-94fa-c8f73332c8f4> tnt:IdentifiedObject.name ?o}"
    )
    assert list(Gjerstad_node)[0][0].value == "Gjerstad"
    assert list(NaN_node)[0][0].value == "NaN"
