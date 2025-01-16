from pathlib import Path

import pytest
from cognite.client import data_modeling as dm

from cognite.neat import NeatSession
from cognite.neat._client import NeatClient
from cognite.neat._issues.errors._general import NeatValueError
from cognite.neat._rules import importers
from tests.data import DATA_DIR, car


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


class TestRulesStoreProvenanceSyncing:
    def test_stopping_reloading_same_model(self, neat_client: NeatClient, tmp_path: Path) -> None:
        neat = NeatSession(neat_client)
        neat.read.excel.examples.pump_example()
        neat.verify()

        # set source to be the same as the target
        target = neat._state.rule_store.provenance[-1].target_entity.result
        target.metadata.source = target.metadata.identifier

        neat.to.excel(tmp_path / "pump_example.xlsx")

        with pytest.raises(NeatValueError) as e:
            neat._state.rule_import(importers.ExcelImporter(tmp_path / "pump_example.xlsx"))

        assert (
            "Imported rules and rules which were used as the source for"
            " them and which are are already in "
            "this neat session have the same data model id"
        ) in e.value.raw_message

    def test_stopping_loading_model_source_mode_not_in(self, neat_client: NeatClient, tmp_path: Path) -> None:
        neat = NeatSession(neat_client)
        neat.read.excel.examples.pump_example()
        neat.verify()

        # set source to be the same as the target
        target = neat._state.rule_store.provenance[-1].target_entity.result
        target.metadata.source = target.metadata.namespace + "some_other_source"

        with pytest.raises(NeatValueError) as e:
            neat._state.rule_import(importers.ExcelImporter(DATA_DIR / "pump_example.xlsx"))

        assert ("Data model source is not in the provenance. Please start a new NEAT session.") in e.value.raw_message
