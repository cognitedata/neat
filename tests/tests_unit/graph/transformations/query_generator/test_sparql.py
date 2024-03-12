import pandas as pd

from cognite.neat.constants import PREFIXES
from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.graph.transformation.query_generator.sparql import build_sparql_query


def test_graph_traversal(source_knowledge_graph: NeatGraphStoreBase):
    # Arrange
    graph = source_knowledge_graph.get_graph()
    rule = "cim:ACLineSegment->cim:BaseVoltage(cim:BaseVoltage.nominalVoltage)"

    # Act
    query = build_sparql_query(graph, rule, PREFIXES)

    # Assert
    df = pd.DataFrame(list(graph.query(query)))
    df.rename(columns={0: "subject", 1: "predicate", 2: "object"}, inplace=True)
    assert str(df.subject[0]) == "http://purl.org/nordic44#_f1769b90-9aeb-11e5-91da-b8763fd99c5f"
