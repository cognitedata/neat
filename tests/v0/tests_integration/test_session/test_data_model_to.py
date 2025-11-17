import datetime
from pathlib import Path

import pytest
import yaml
from cognite.client import data_modeling as dm
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._data_model import importers
from cognite.neat.v0.core._issues.errors._general import NeatValueError
from tests.v0.data import GraphData, SchemaData


def create_new_car_model(neat_client: NeatClient, schema_space: str, instance_space: str) -> dm.DataModelId:
    # Creating a copy of the model to avoid modifying the original
    car = GraphData.car
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
    @pytest.mark.skip("Skipping test as it has tendecy to clash with other tests")
    def test_to_cdf_recreate(self, neat_client: NeatClient) -> None:
        car_model = create_new_car_model(neat_client, "test_to_cdf_recreate", "test_to_cdf_recreate_data")
        neat = NeatSession(neat_client)
        neat.read.cdf.data_model(car_model)

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

    @pytest.mark.skip("This is flaky and we do not maintain v0 any more")
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


@pytest.mark.skip("This test is flaky and we do not maintain v0 any more")
class TestRulesStoreProvenanceSyncing:
    def test_detached_provenance(self, tmp_path: Path) -> None:
        neat = NeatSession()
        neat.read.examples.nordic44()
        neat.infer()
        neat.show.data_model()
        neat.to.excel(tmp_path / "nordic44.xlsx")
        neat.fix.data_model.cdf_compliant_external_ids()

        with pytest.raises(NeatValueError) as e:
            neat._state.data_model_import(
                importers.ExcelImporter(tmp_path / "nordic44.xlsx"),
                enable_manual_edit=True,
            )

        assert (
            "Imported data model is detached from the provenance chain."
            " Import will be skipped. Start a new NEAT session and "
            "import the data model there."
        ) in e.value.raw_message

    def test_unknown_source(self, neat_client: NeatClient) -> None:
        neat = NeatSession(neat_client)
        neat.read.examples.pump_example()

        with pytest.raises(NeatValueError) as e:
            neat._state.data_model_import(
                importers.ExcelImporter(SchemaData.Physical.dms_unknown_value_type_xlsx),
                enable_manual_edit=True,
            )

        assert "The source of the imported data model is unknown" in e.value.raw_message

    def test_source_not_in_store(self, tmp_path: Path, neat_client: NeatClient) -> None:
        neat = NeatSession(neat_client)
        neat.read.examples.pump_example()
        neat.to.excel(tmp_path / "pump.xlsx")

        neat2 = NeatSession(neat_client)
        neat2.read.examples.nordic44()
        neat2.infer()

        with pytest.raises(NeatValueError) as e:
            neat2._state.data_model_import(
                importers.ExcelImporter(tmp_path / "pump.xlsx"),
                enable_manual_edit=True,
            )

        assert "The source of the imported data model is not in the provenance" in e.value.raw_message

    def test_external_mod_allowed_provenance(self, tmp_path: Path) -> None:
        neat = NeatSession()
        neat.read.examples.nordic44()
        neat.infer()
        neat.fix.data_model.cdf_compliant_external_ids()
        neat.to.excel(tmp_path / "nordic44.xlsx")
        neat.read.excel(
            tmp_path / "nordic44.xlsx",
            enable_manual_edit=True,
        )

        assert len(neat._state.data_model_store.provenance) == 3
        assert (
            neat._state.data_model_store.provenance[-1].description
            == "Manual transformation of data model outside of NEAT"
        )

    def test_raw_filter(self, neat_client: NeatClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(neat_client)
        neat.read.excel(SchemaData.Physical.dm_raw_filter_xlsx)

        rules = neat._state.data_model_store.last_verified_physical_data_model
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        neat.to.cdf.data_model(existing="recreate")

        neat = NeatSession(neat_client)
        neat.read.cdf.data_model(("nikola_space", "nikola_external_id", "v1"))

        rules = neat._state.data_model_store.last_verified_physical_data_model
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        rules_str = neat.to.yaml(format="neat")
        rules_dict = yaml.safe_load(rules_str)

        data_regression.check(
            {
                "rules": rules_dict,
            }
        )
