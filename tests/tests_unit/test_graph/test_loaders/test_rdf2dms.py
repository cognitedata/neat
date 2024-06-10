import pytest

from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.graph.stores import NeatGraphStore
from tests.data import car


@pytest.fixture()
def car_case() -> NeatGraphStore:
    print(car.CAR_RULES)
    store = NeatGraphStore.from_memory_store(rules=car.CAR_RULES)

    for triple in car.TRIPLES:
        store.graph.add(triple)
    return store


class TestDMSLoader:
    def test_load_car_example(self, car_case: NeatGraphStore) -> None:
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
