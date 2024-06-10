import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.graph.stores import NeatGraphStore
from tests.data import car


@pytest.fixture()
def deployed_car_model(cognite_client: CogniteClient) -> dm.DataModelId:
    cognite_client.data_modeling.spaces.apply([dm.SpaceApply(s) for s in [car.MODEL_SPACE, car.INSTANCE_SPACE]])
    cognite_client.data_modeling.instances.apply(car.NODE_TYPES)
    cognite_client.data_modeling.containers.apply(car.CONTAINERS)
    write_model = car.CAR_MODEL.as_write()
    created = cognite_client.data_modeling.data_models.apply(write_model)
    yield created.as_id()


@pytest.fixture()
def car_store() -> NeatGraphStore:
    store = NeatGraphStore.from_memory_store(rules=car.CAR_RULES)

    for triple in car.TRIPLES:
        store.graph.add(triple)
    return store


class TestDMSLoader:
    def test_load_car_example(
        self, cognite_client: CogniteClient, deployed_car_model: dm.DataModelId, car_store: NeatGraphStore
    ) -> None:
        loader = DMSLoader.from_data_model_id(cognite_client, deployed_car_model, car_store, car.INSTANCE_SPACE)

        result = loader.load_into_cdf(cognite_client, dry_run=False)

        assert len(result) == 1

        assert len(result[0].success) == len(car.INSTANCES)
