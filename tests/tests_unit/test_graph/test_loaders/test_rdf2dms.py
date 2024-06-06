import pytest

from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.graph.stores import MemoryStore
from tests.data import car


@pytest.fixture()
def car_case() -> MemoryStore:
    store = MemoryStore()
    store.init_graph()
    store.add_triples(car.TRIPLES)
    return store


class TestDMSLoader:
    def test_load_car_example(self, car_case: MemoryStore) -> None:
        loader = DMSLoader(
            car_case,
            car.CAR_MODEL,
            car.INSTANCE_SPACE,
            {
                car.CAR_MODEL.views[0].as_id(): "Car",
                car.CAR_MODEL.views[1].as_id(): "Manufacturer",
                car.CAR_MODEL.views[2].as_id(): "Color",
            },
        )

        loaded = loader.load(stop_on_exception=True)

        assert [inst.dump() for inst in loaded] == [inst.dump() for inst in car.INSTANCES]
