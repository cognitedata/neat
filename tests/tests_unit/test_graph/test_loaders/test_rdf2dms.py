import pytest
from cognite.client import data_modeling as dm
from rdflib import Namespace
from rdflib.term import URIRef

from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.graph.stores import MemoryStore


@pytest.fixture()
def car_case() -> MemoryStore:
    store = MemoryStore(namespace=Namespace("http://example.com/"), prefixes={"ex": "http://example.com/"})
    store.init_graph()
    store.add_triples(
        [
            (URIRef("ex:Car1"), URIRef("rdf:type"), URIRef("ex:Car")),
            (URIRef("ex:Car1"), URIRef("ex:make"), URIRef("Toyota")),
            (URIRef("ex:Car1"), URIRef("ex:year"), URIRef("2020")),
            (URIRef("ex:Car1"), URIRef("ex:color"), URIRef("Blue")),
            (URIRef("ex:Car2"), URIRef("rdf:type"), URIRef("ex:Car")),
            (URIRef("ex:Car2"), URIRef("ex:make"), URIRef("Ford")),
            (URIRef("ex:Car2"), URIRef("ex:year"), URIRef("2018")),
            (URIRef("ex:Car2"), URIRef("ex:color"), URIRef("Red")),
        ]
    )
    return store


class TestDMSLoader:
    def test_load_car_example(self, car_case: MemoryStore) -> None:
        expected_nodes = [
            dm.NodeApply(
                space="sp_example",
                external_id="Car1",
                sources=[
                    dm.NodeOrEdgeData(
                        source=CAR_MODEL.views[0].as_id(), properties={"make": "Toyota", "year": 2020, "color": "Blue"}
                    )
                ],
            ),
            dm.NodeApply(
                space="sp_example",
                external_id="Car2",
                sources=[
                    dm.NodeOrEdgeData(
                        source=CAR_MODEL.views[0].as_id(), properties={"make": "Ford", "year": 2018, "color": "Red"}
                    )
                ],
            ),
        ]
        loader = DMSLoader(car_case, CAR_MODEL, {CAR_MODEL.views[0].as_id(): URIRef("ex:Car")})

        loaded = loader.load(stop_on_exception=True)

        assert list(loaded) == expected_nodes


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
            version=1,
            properties={
                "make": dm.MappedProperty(
                    container=dm.ContainerId("my_example", "Car"),
                    container_property_identifier="make",
                    type=dm.Text(),
                    nullable=False,
                    auto_increment=False,
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
        )
    ],
)
