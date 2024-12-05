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

    original_instance_space = car.INSTANCE_SPACE
    new_instance_space = f"{new_space}_data"
    nodes = dm.NodeApplyList.load(
        dm.NodeApplyList([node for node in car.INSTANCES if isinstance(node, dm.NodeApply)])
        .dump_yaml()
        .replace(original_instance_space, new_instance_space)
        .replace(original_space, new_space)
    )
    edges = dm.EdgeApplyList.load(
        dm.EdgeApplyList([edge for edge in car.INSTANCES if isinstance(edge, dm.EdgeApply)])
        .dump_yaml()
        .replace(original_instance_space, new_instance_space)
        .replace(original_space, new_space)
    )

    neat_client.data_modeling.spaces.apply(dm.SpaceApply(space=new_instance_space))
    neat_client.data_modeling.instances.apply(nodes, edges)

    return model_copy.as_id()


class TestDataModelToCDF:
    def test_to_cdf_recreate(self, neat_client: NeatClient, car_model: dm.DataModelId) -> None:
        neat = NeatSession(neat_client)

        neat.read.cdf.data_model(car_model)

        neat.verify()

        result = neat.to.cdf.data_model(existing="recreate", drop_data=False)
        result_by_name = {r.name: r for r in result}
        # The model contain data, so should skip space and container
        assert len(result_by_name["spaces"].skipped) == 1
        assert len(result_by_name["containers"].skipped) == 3
        # The views and data model should have been recreated, i.e., deleted and created
        assert len(result_by_name["views"].deleted) == 3
        assert len(result_by_name["views"].created) == 3
        assert len(result_by_name["data_models"].deleted) == 1
        assert len(result_by_name["data_models"].created) == 1
