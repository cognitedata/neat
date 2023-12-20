import pprint

import pytest
from IPython.display import Markdown, display
from pydantic import ValidationError

from cognite.neat.constants import PREFIXES
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformations.query_generator import build_sparql_query
from cognite.neat.rules.models.rdfpath import (
    AllProperties,
    AllReferences,
    Entity,
    Hop,
    SingleProperty,
    Step,
    TransformationRuleType,
    is_rawlookup,
    is_rdfpath,
    parse_rule,
    parse_traversal,
)
from cognite.neat.rules.models.rules import Property
from tests import config

nan = float("nan")


def generate_valid_property_test_data():
    yield pytest.param(
        {
            "Class": "GeographicalRegion",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "*",
            "Type": "nan",
            "Rule Type": "rdfpath",
            "Rule": "cim:GeographicalRegion(*)",
        },
        id="Valid rdfpath rule",
    )
    yield pytest.param(
        {
            "Class": "Terminal",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "Terminal.Substation",
            "Type": "nan",
            "Rule Type": "rawlookup",
            "Rule": "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation | "
            "TableName(Lookup, ValueColumn)",
        },
        id="Valid rawlookup rule",
    )


@pytest.mark.parametrize("raw_input", generate_valid_property_test_data())
def test_creating_valid_property(raw_input: dict):
    assert Property(**raw_input)


def generate_invalid_property_test_data():
    yield pytest.param(
        {
            "Class": "GeographicalRegion",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "*",
            "Type": "nan",
            "Rule Type": "rdfpath",
            "Rule": "GeographicalRegion(*)",
        },
        id="Invalid rdfpath rule",
    )
    yield pytest.param(
        {
            "Class": "Terminal",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "Terminal.Substation",
            "Type": "nan",
            "Rule Type": "rawlookup",
            "Rule": "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation | TableName(Lookup, )",
        },
        id="Invalid rawlookup rule",
    )


@pytest.mark.parametrize("raw_input", generate_invalid_property_test_data())
def test_creating_invalid_property(raw_input: dict):
    with pytest.raises(ValidationError):
        Property(**raw_input)


def generate_is_rdfpath_test_data():
    yield pytest.param("GeographicalRegion(*)", False, id="One to many missing namespace")
    yield pytest.param("cim:GeographicalRegion(*)", True, id="Valid One to many")
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation", True, id="Valid parent path"
    )


@pytest.mark.parametrize("raw_input, is_rdfpath_expected", generate_is_rdfpath_test_data())
def test_is_rdfpath(raw_input: str, is_rdfpath_expected: bool):
    assert is_rdfpath(raw_input) is is_rdfpath_expected


def generate_is_rawlookup_test_data():
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation | TableName(Lookup, ValueColumn)",
        True,
        id="Valid parent path with table lookup",
    )
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation TableName(Lookup, ValueColumn)",
        False,
        id="Missing piping operator",
    )
    yield pytest.param("cim:GeographicalRegion(*) | TableName(Lookup,)", False, id="Missing value column")


@pytest.mark.parametrize("raw_input, is_rawlookup_expected", generate_is_rawlookup_test_data())
def test_is_rawlookup(raw_input: str, is_rawlookup_expected: bool):
    assert is_rawlookup(raw_input) is is_rawlookup_expected


def generate_parse_traversal():
    yield pytest.param(
        "cim:GeographicalRegion(*)",
        AllProperties(
            class_=Entity(prefix="cim", suffix="GeographicalRegion", name="GeographicalRegion", type_="class")
        ),
        id="All properties",
    )
    yield pytest.param(
        "cim:GeographicalRegion(cim:RootCIMNode.node)",
        SingleProperty(
            class_=Entity(prefix="cim", suffix="GeographicalRegion", name="GeographicalRegion", type_="class"),
            property=Entity(prefix="cim", suffix="RootCIMNode.node", name="RootCIMNode.node", type_="property"),
        ),
        id="Single property",
    )
    yield pytest.param(
        "cim:GeographicalRegion",
        AllReferences(
            class_=Entity(prefix="cim", suffix="GeographicalRegion", name="GeographicalRegion", type_="class")
        ),
        id="All references",
    )
    yield pytest.param(
        "cim:G",
        AllReferences(class_=Entity(prefix="cim", suffix="G", name="G", type_="class")),
        id="All references single character name",
    )
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation",
        Hop.from_string(
            class_="cim:Terminal",
            traversal=[
                Step.from_string(raw=step)
                for step in ["->cim:ConnectivityNode", "->cim:VoltageLevel", "->cim:Substation"]
            ],
        ),
        id="Child traversal without property",
    )
    yield pytest.param(
        "cim:T->cim:C->cim:V->cim:S",
        Hop.from_string(
            class_="cim:T",
            traversal=[Step.from_string(raw=step) for step in ["->cim:C", "->cim:V", "->cim:S"]],
        ),
        id="Child traversal without property single character name",
    )
    yield pytest.param(
        "cim:Substation<-cim:VoltageLevel<-cim:ConnectivityNode<-cim:Terminal",
        Hop.from_string(
            class_="cim:Substation",
            traversal=[
                Step.from_string(raw=step)
                for step in ["<-cim:VoltageLevel", "<-cim:ConnectivityNode", "<-cim:Terminal"]
            ],
        ),
        id="Parent traversal without property",
    )
    yield pytest.param(
        "cim:HydroPump<-cim:SynchronousMachine->cim:VoltageLevel->cim:Substation",
        Hop.from_string(
            class_="cim:HydroPump",
            traversal=[
                Step.from_string(raw=step)
                for step in ["<-cim:SynchronousMachine", "->cim:VoltageLevel", "->cim:Substation"]
            ],
        ),
        id="Bidirectional traversal without property",
    )

    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation(cim:IdentifiedObject.name)",
        Hop.from_string(
            class_="cim:Terminal",
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
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:S(cim:n)",
        Hop.from_string(
            class_="cim:Terminal",
            traversal=[
                Step.from_string(raw=step)
                for step in [
                    "->cim:ConnectivityNode",
                    "->cim:VoltageLevel",
                    "->cim:S(cim:n)",
                ]
            ],
        ),
        id="Child traversal with single character property",
    )
    yield pytest.param(
        "cim:Substation<-cim:VoltageLevel<-cim:ConnectivityNode<-cim:Terminal(cim:IdentifiedObject.name)",
        Hop.from_string(
            class_="cim:Substation",
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
        Hop.from_string(
            class_="cim:HydroPump",
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
    raw: str, expected_traversal: AllProperties | AllReferences | Entity | Hop | SingleProperty, name: str | None = None
):
    global GRAPH
    if name:
        display(Markdown(f"# {name}"))
    display(Markdown("## Raw String"))
    display(Markdown(raw))
    display(Markdown("## Parsed Traversal"))
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(expected_traversal.dict())

    rule = parse_rule(raw, TransformationRuleType.rdfpath)
    if isinstance(rule, TransformationRuleType):
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
        display_test_parse_traversal(*parameters.values, suffix=parameters.id)
