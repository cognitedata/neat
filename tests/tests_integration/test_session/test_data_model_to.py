import pytest
from cognite.client import data_modeling as dm

from cognite.neat import NeatSession
from cognite.neat._client import NeatClient
from tests.data import car


@pytest.fixture
def car_model(neat_client: NeatClient) -> dm.DataModelId:
    # Creating a copy of the model to avoid modifying the original
    original_space = car.CAR_MODEL.space
    new_space = "test_to_cdf_recreate"
    raw_yaml = car.CONTAINERS.dump_yaml().replace(original_space, new_space)
    container_copy = dm.ContainerApplyList.load(raw_yaml)

    raw_yaml = car.CAR_MODEL.dump_yaml().replace(original_space, new_space)
    model_copy = dm.DataModel.load(raw_yaml)

    neat_client.data_modeling.spaces.apply(dm.SpaceApply(space=new_space))
    neat_client.data_modeling.containers.apply(container_copy)
    neat_client.data_modeling.data_models.apply(model_copy)
    return model_copy.as_id()


class TestDataModelToCDF:
    def test_to_cdf_recreate(self, neat_client: NeatClient, car_model: dm.DataModelId) -> None:
        neat = NeatSession(neat_client)

        neat.read.cdf.data_model(car_model)

        neat.verify()

        result = neat.to.cdf.data_model(existing="recreate")

        assert len(result) == 6
