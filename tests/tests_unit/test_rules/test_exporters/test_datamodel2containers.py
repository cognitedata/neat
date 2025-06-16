from pathlib import Path

import pytest
from cognite.client.data_classes.data_modeling import ContainerApplyList

from cognite.neat.core._client._deploy import ExistingResource
from cognite.neat.core._client.data_classes.deploy_result import DeployResult
from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._data_model.exporters import ContainerExporter
from tests.data import GraphData
from tests.utils import as_read_containers


class TestContainerExporter:
    def test_export_valid_data_model(self, tmp_path: Path) -> None:
        some_model = GraphData.car.get_car_dms_rules()

        exporter = ContainerExporter()
        exporter.export_to_file(some_model, tmp_path / "car.Containers.yaml")

        assert (tmp_path / "car.Containers.yaml").exists()

        containers = exporter.export(some_model)

        assert isinstance(containers, ContainerApplyList)

        with monkeypatch_neat_client() as client:
            client.data_modeling.containers.apply.return_value = as_read_containers(containers)
            result = exporter.deploy(some_model, client)

        assert isinstance(result, DeployResult)
        assert result.status == "success"
        assert len(result.created) == len(some_model.containers)

    @pytest.mark.parametrize("existing", ["force", "recreate"])
    def test_export_invalid_args(self, existing: ExistingResource) -> None:
        exporter = ContainerExporter(existing=existing, drop_data=False)

        with pytest.raises(ValueError) as exc_info:
            exporter.export(GraphData.car.get_car_dms_rules())

        assert str(exc_info.value) == (
            "NeatValueError: Failed container export. Cannot export containers with "
            "exising='recreate' or 'force' without risk dropping data. Set drop_data=True to proceed."
        )
