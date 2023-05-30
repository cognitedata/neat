from rdflib import Literal

from cognite.neat.core.extractors import sheet2graph
from cognite.neat.core.utils import remove_namespace


def test_sheet2graph(simple_rules, graph_capturing_sheet):
    graph = sheet2graph(graph_capturing_sheet, simple_rules)

    count_dict = {
        remove_namespace(res[0]): int(res[1])
        for res in list(
            graph.query(
                "SELECT ?class (count(?s) as ?instances ) WHERE { ?s a ?class . } group by ?class order by DESC(?instances)"
            )
        )
    }
    assert list(graph.query("Select ?o WHERE { neat:Country-1 neat:TSO ?o }"))[0][0] == Literal("Statnett")
    assert count_dict == {"PriceArea": 2, "CountryGroup": 1, "Country": 1, "PriceAreaConnection": 1}
