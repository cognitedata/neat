import pprint

import pytest
from IPython.display import Markdown, display

from cognite.neat.core.configuration import PREFIXES
from cognite.neat.core.loader.graph_store import NeatGraphStore
from cognite.neat.core.query_generator import build_sparql_query
from cognite.neat.core.rules.to_rdf_path import (
    AllProperties,
    AllReferences,
    Entity,
    Hop,
    RuleType,
    SingleProperty,
    Step,
    parse_rule,
    parse_traversal,
)
from tests import config


def generate_parse_traversal():
    yield pytest.param(
        "cim:GeographicalRegion(*)",
        AllProperties(class_=Entity(prefix="cim", name="GeographicalRegion")),
        id="All properties",
    )
    yield pytest.param(
        "cim:GeographicalRegion(cim:RootCIMNode.node)",
        SingleProperty(
            class_=Entity(prefix="cim", name="GeographicalRegion"),
            property=Entity(prefix="cim", name="RootCIMNode.node"),
        ),
        id="Single property",
    )
    yield pytest.param(
        "cim:GeographicalRegion",
        AllReferences(
            class_=Entity(prefix="cim", name="GeographicalRegion"),
        ),
        id="All references",
    )
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation",
        Hop(
            origin="cim:Terminal",
            traversal=[
                Step.from_string(raw=step)
                for step in ["->cim:ConnectivityNode", "->cim:VoltageLevel", "->cim:Substation"]
            ],
        ),
        id="Child traversal without property",
    )
    yield pytest.param(
        "cim:Substation<-cim:VoltageLevel<-cim:ConnectivityNode<-cim:Terminal",
        Hop(
            origin="cim:Substation",
            traversal=[
                Step.from_string(raw=step)
                for step in ["<-cim:VoltageLevel", "<-cim:ConnectivityNode", "<-cim:Terminal"]
            ],
        ),
        id="Parent traversal without property",
    )
    yield pytest.param(
        "cim:HydroPump<-cim:SynchronousMachine->cim:VoltageLevel->cim:Substation",
        Hop(
            origin="cim:HydroPump",
            traversal=[
                Step.from_string(raw=step)
                for step in ["<-cim:SynchronousMachine", "->cim:VoltageLevel", "->cim:Substation"]
            ],
        ),
        id="Bidirectional traversal without property",
    )

    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation(cim:IdentifiedObject.name)",
        Hop(
            origin="cim:Terminal",
            traversal=[
                Step.from_string(raw=step)
                for step in [
                    "->cim:ConnectivityNode",
                    "->cim:VoltageLevel",
                    "->cim:Substation(cim:IdentifiedObject.name)",
                ]
            ],
        ),
        id="Child traversal with property",
    )
    yield pytest.param(
        "cim:Substation<-cim:VoltageLevel<-cim:ConnectivityNode<-cim:Terminal(cim:IdentifiedObject.name)",
        Hop(
            origin="cim:Substation",
            traversal=[
                Step.from_string(raw=step)
                for step in [
                    "<-cim:VoltageLevel",
                    "<-cim:ConnectivityNode",
                    "<-cim:Terminal(cim:IdentifiedObject.name)",
                ]
            ],
        ),
        id="Parent traversal with property",
    )
    yield pytest.param(
        "cim:HydroPump<-cim:SynchronousMachine->cim:VoltageLevel->cim:Substation(cim:IdentifiedObject.name)",
        Hop(
            origin="cim:HydroPump",
            traversal=[
                Step.from_string(raw=step)
                for step in [
                    "<-cim:SynchronousMachine",
                    "->cim:VoltageLevel",
                    "->cim:Substation(cim:IdentifiedObject.name)",
                ]
            ],
        ),
        id="Bidirectional traversal with property",
    )


@pytest.mark.parametrize("raw, expected_traversal", generate_parse_traversal())
def test_parse_traversal(raw: str, expected_traversal: AllProperties):
    # Act
    actual_traversal = parse_traversal(raw)

    # Assert
    assert type(actual_traversal) == type(expected_traversal)
    assert actual_traversal.model_dump_json(indent=4) == expected_traversal.model_dump_json(indent=4)


def _load_nordic_knowledge_graph():
    graph = NeatGraphStore(namespace=PREFIXES["nordic44"])
    graph.init_graph()
    graph.import_from_file(config.NORDIC44_KNOWLEDGE_GRAPH)
    return graph


GRAPH = None


def display_test_parse_traversal(
    raw: str,
    expected_traversal: AllProperties | AllReferences | Entity | Hop | SingleProperty,
    name: str = None,
):
    global GRAPH
    if name:
        display(Markdown(f"# {name}"))
    display(Markdown("## Raw String"))
    display(Markdown(raw))
    display(Markdown("## Parsed Traversal"))
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(expected_traversal.dict())

    rule = parse_rule(raw, RuleType.rdfpath)
    if isinstance(rule, RuleType):
        # Picking up rdf:type is done by default
        query = ""
    else:
        if GRAPH is None:
            GRAPH = _load_nordic_knowledge_graph()
        try:
            query = build_sparql_query(GRAPH, rule.traversal, PREFIXES)
        except Exception as e:
            query = f"Failed to generate query: {e}"
    display(Markdown("## Resulting SparkQL"))
    display(Markdown(query))


if __name__ == "__main__":
    for parameters in generate_parse_traversal():
        display_test_parse_traversal(*parameters.values, name=parameters.id)
