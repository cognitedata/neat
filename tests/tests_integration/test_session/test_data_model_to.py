from cognite.client import data_modeling as dm

from cognite.neat import NeatSession
from cognite.neat._client import NeatClient
from tests.data import car


def create_new_car_model(neat_client: NeatClient, schema_space: str, instance_space: str) -> dm.DataModelId:
    # Creating a copy of the model to avoid modifying the original
    original_space = car.CAR_MODEL.space
    raw_yaml = car.CONTAINERS.dump_yaml().replace(original_space, schema_space)
    container_copy = dm.ContainerApplyList.load(raw_yaml)

    raw_yaml = car.CAR_MODEL.dump_yaml().replace(original_space, schema_space)
    model_copy = dm.DataModel.load(raw_yaml)

    neat_client.data_modeling.spaces.apply(dm.SpaceApply(space=schema_space))
    neat_client.data_modeling.containers.apply(container_copy)
    neat_client.data_modeling.data_models.apply(model_copy)

    original_instance_space = car.INSTANCE_SPACE
    nodes = dm.NodeApplyList.load(
        dm.NodeApplyList([node for node in car.INSTANCES if isinstance(node, dm.NodeApply)])
        .dump_yaml()
        .replace(original_instance_space, instance_space)
        .replace(original_space, schema_space)
    )
    edges = dm.EdgeApplyList.load(
        dm.EdgeApplyList([edge for edge in car.INSTANCES if isinstance(edge, dm.EdgeApply)])
        .dump_yaml()
        .replace(original_instance_space, instance_space)
        .replace(original_space, schema_space)
    )

    neat_client.data_modeling.spaces.apply(dm.SpaceApply(space=instance_space))
    neat_client.data_modeling.instances.apply(nodes, edges)

    return model_copy.as_id()


class TestDataModelToCDF:
    def test_to_cdf_recreate(self, neat_client: NeatClient) -> None:
        car_model = create_new_car_model(neat_client, "test_to_cdf_recreate", "test_to_cdf_recreate_data")
        neat = NeatSession(neat_client)

        neat.read.cdf.data_model(car_model)

        neat.verify()

        result = neat.to.cdf.data_model(existing="recreate", drop_data=False)
        result_by_name = {r.name: r for r in result}
        spaces = result_by_name["spaces"]
        assert len(spaces.changed | spaces.created | spaces.unchanged) == 1
        # The model contain data, so should skip container
        assert len(result_by_name["containers"].skipped) == 3
        # The views and data model should have been recreated, i.e., deleted and created
        assert len(result_by_name["views"].deleted) == 3
        assert len(result_by_name["views"].created) == 3
        assert len(result_by_name["data_models"].deleted) == 1
        assert len(result_by_name["data_models"].created) == 1

    def test_to_cdf_recreate_drop_data(self, neat_client: NeatClient) -> None:
        car_model = create_new_car_model(
            neat_client, "test_to_cdf_recreate_drop_data", "test_to_cdf_recreate_drop_data_data"
        )
        neat = NeatSession(neat_client)

        neat.read.cdf.data_model(car_model)

        neat.verify()

        result = neat.to.cdf.data_model(existing="recreate", drop_data=True)
        result_by_name = {r.name: r for r in result}
        # Spaces are not deleted, instead they are updated.
        spaces = result_by_name["spaces"]
        assert len(spaces.changed | spaces.created | spaces.unchanged) == 1
        # The views and data model should have been recreated, i.e., deleted and created
        assert len(result_by_name["containers"].deleted) == 3
        assert len(result_by_name["containers"].created) == 3
        assert len(result_by_name["views"].deleted) == 3
        assert len(result_by_name["views"].created) == 3
        assert len(result_by_name["data_models"].deleted) == 1
        assert len(result_by_name["data_models"].created) == 1
