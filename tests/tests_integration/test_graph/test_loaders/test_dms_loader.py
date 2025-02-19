import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat._client import NeatClient
from cognite.neat._graph.loaders import DMSLoader
from cognite.neat._rules.importers import InferenceImporter
from cognite.neat._store import NeatGraphStore
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
    store = NeatGraphStore.from_memory_store()
    store.add_rules(car.get_care_rules())

    for triple in car.TRIPLES:
        store.dataset.add(triple)

    rules = InferenceImporter.from_graph_store(store).to_rules().rules.as_verified_rules()
    store.add_rules(rules)

    return store


class TestDMSLoader:
    @pytest.mark.skip("This test needs to be rewritten and test data updated!")
    def test_load_car_example(
        self, neat_client: NeatClient, deployed_car_model: dm.DataModelId, car_store: NeatGraphStore
    ) -> None:
        loader = DMSLoader.from_data_model_id(neat_client, deployed_car_model, car_store, car.INSTANCE_SPACE)

        result = loader.load_into_cdf(neat_client, dry_run=False)

        assert len(result) == 4

        assert sum(item.success for item in result) == len(car.INSTANCES)
