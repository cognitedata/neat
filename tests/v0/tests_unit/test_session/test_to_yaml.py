from pathlib import Path

from cognite.neat import NeatSession
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.importers import BaseImporter
from cognite.neat.v0.core._data_model.models import UnverifiedPhysicalDataModel
from tests.v0.data import SchemaData


class RuleImporter(BaseImporter):
    def to_data_model(self) -> ImportedDataModel[UnverifiedPhysicalDataModel]:
        return ImportedDataModel(SchemaData.NonNeatFormats.windturbine.INPUT_RULES, {})


class TestToYaml:
    def test_to_yaml(self, tmp_path: Path) -> None:
        neat = NeatSession()
        # Hack to read in model.
        neat._state.data_model_store.import_data_model(RuleImporter())

        neat.verify()
        neat.to.yaml(tmp_path, format="toolkit")

        files = list(tmp_path.rglob("*.yaml"))
        assert len(files) == 9
