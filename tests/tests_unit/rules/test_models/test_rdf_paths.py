import pytest

from cognite.neat._rules.models._rdfpath import (
    Entity,
    Hop,
    SingleProperty,
    Step,
    Traversal,
    parse_traversal,
)


def generate_parse_traversal():
    yield pytest.param(
        "cim:GeographicalRegion(cim:RootCIMNode.node)",
        SingleProperty(
            class_=Entity(prefix="cim", suffix="GeographicalRegion"),
            property=Entity(prefix="cim", suffix="RootCIMNode.node"),
        ),
        id="Single property",
    )
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation",
        Hop(
            class_=Entity.from_string("cim:Terminal"),
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
            class_=Entity.from_string("cim:Substation"),
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
            class_=Entity.from_string("cim:HydroPump"),
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
            class_=Entity.from_string("cim:Terminal"),
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
            class_=Entity.from_string("cim:Substation"),
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
            class_=Entity.from_string("cim:HydroPump"),
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
def test_parse_traversal(raw: str, expected_traversal: Traversal):
    # Act
    actual_traversal = parse_traversal(raw)

    # Assert
    assert type(actual_traversal) is type(expected_traversal)
    assert actual_traversal.model_dump() == expected_traversal.model_dump()
