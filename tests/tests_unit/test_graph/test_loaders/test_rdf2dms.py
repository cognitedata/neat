import pytest
from cognite.client import data_modeling as dm
from rdflib import RDF
from rdflib.term import Literal

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.graph.stores import MemoryStore


@pytest.fixture()
def car_case() -> MemoryStore:
    store = MemoryStore()
    store.init_graph()
    neat = DEFAULT_NAMESPACE
    store.add_triples(
        [
            (neat["Toyota"], RDF.type, neat["Manufacturer"]),
            (neat["Toyota"], neat["name"], Literal("Toyota")),
            (neat["Car1"], RDF.type, neat["Car"]),
            (neat["Car1"], neat["make"], neat["Toyota"]),
            (neat["Car1"], neat["year"], Literal("2020")),
            (neat["Car1"], neat["color"], Literal("Blue")),
            (neat["Ford"], RDF.type, neat["Manufacturer"]),
            (neat["Ford"], neat["name"], Literal("Ford")),
            (neat["Car2"], RDF.type, neat["Car"]),
            (neat["Car2"], neat["make"], neat["Ford"]),
            (neat["Car2"], neat["year"], Literal("2018")),
            (neat["Car2"], neat["color"], Literal("Red")),
        ]
    )
    return store


class TestDMSLoader:
    def test_load_car_example(self, car_case: MemoryStore) -> None:
        instance_space = "sp_cars"
        expected_nodes = [
            dm.NodeApply(
                space=instance_space,
                external_id="Car1",
                sources=[
                    dm.NodeOrEdgeData(source=CAR_MODEL.views[0].as_id(), properties={"year": 2020, "color": "Blue"})
                ],
            ),
            dm.EdgeApply(
                space=instance_space,
                external_id="Car1.make.Toyota",
                type=dm.DirectRelationReference("sp_example", "Car.Manufacturer"),
                start_node=dm.DirectRelationReference(instance_space, "Car1"),
                end_node=dm.DirectRelationReference(instance_space, "Toyota"),
            ),
            dm.NodeApply(
                space=instance_space,
                external_id="Car2",
                sources=[
                    dm.NodeOrEdgeData(source=CAR_MODEL.views[0].as_id(), properties={"year": 2018, "color": "Red"})
                ],
            ),
            dm.EdgeApply(
                space=instance_space,
                external_id="Car2.make.Ford",
                type=dm.DirectRelationReference("sp_example", "Car.Manufacturer"),
                start_node=dm.DirectRelationReference(instance_space, "Car2"),
                end_node=dm.DirectRelationReference(instance_space, "Ford"),
            ),
            dm.NodeApply(
                space=instance_space,
                external_id="Ford",
                sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[1].as_id(), properties={"name": "Ford"})],
            ),
            dm.NodeApply(
                space=instance_space,
                external_id="Toyota",
                sources=[dm.NodeOrEdgeData(source=CAR_MODEL.views[1].as_id(), properties={"name": "Toyota"})],
            ),
        ]
        loader = DMSLoader(
            car_case,
            CAR_MODEL,
            instance_space,
            {CAR_MODEL.views[0].as_id(): "Car", CAR_MODEL.views[1].as_id(): "Manufacturer"},
        )

        loaded = loader.load(stop_on_exception=True)

        assert [inst.dump() for inst in loaded] == [inst.dump() for inst in expected_nodes]


CAR_MODEL: dm.DataModel[dm.View] = dm.DataModel(
    space="sp_example",
    external_id="Car Model",
    version="1",
    is_global=False,
    name=None,
    description=None,
    last_updated_time=1,
    created_time=1,
    views=[
        dm.View(
            space="sp_example",
            external_id="Car",
            version="1",
            properties={
                "make": dm.MultiEdgeConnection(
                    source=dm.ViewId("sp_example", "Manufacturer", "1"),
                    type=dm.DirectRelationReference("sp_example", "Car.Manufacturer"),
                    name=None,
                    description=None,
                    edge_source=None,
                    direction="outwards",
                ),
                "year": dm.MappedProperty(
                    container=dm.ContainerId("my_example", "Car"),
                    container_property_identifier="year",
                    type=dm.Int64(),
                    nullable=False,
                    auto_increment=False,
                ),
                "color": dm.MappedProperty(
                    container=dm.ContainerId("my_example", "Car"),
                    container_property_identifier="color",
                    type=dm.Text(),
                    nullable=False,
                    auto_increment=False,
                ),
            },
            last_updated_time=0,
            created_time=0,
            description=None,
            name=None,
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            is_global=False,
        ),
        dm.View(
            space="sp_example",
            external_id="Manufacturer",
            version="1",
            properties={
                "name": dm.MappedProperty(
                    container=dm.ContainerId("my_example", "Manufacturer"),
                    container_property_identifier="name",
                    type=dm.Text(),
                    nullable=False,
                    auto_increment=False,
                ),
            },
            last_updated_time=0,
            created_time=0,
            description=None,
            name=None,
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            is_global=False,
        ),
    ],
)
