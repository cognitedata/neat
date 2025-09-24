from pathlib import Path

from cognite.neat.v0.core._data_model.exporters import YAMLExporter
from cognite.neat.v0.core._data_model.importers._dict2data_model import DictImporter
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel


class TestYAMLExporter:
    def test_export_import_rules(self, alice_rules: PhysicalDataModel, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(alice_rules, tmp_path / "tmp.yaml")
        importer = DictImporter.from_yaml_file(tmp_path / "tmp.yaml")

        recreated_rules = importer.to_data_model().unverified_data_model.as_verified_data_model()

        assert alice_rules.dump() == recreated_rules.dump()

    def test_export_import_information_rules(self, david_rules: ConceptualDataModel, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(david_rules, tmp_path / "tmp.yaml")
        importer = DictImporter.from_yaml_file(tmp_path / "tmp.yaml")

        recreated_rules = importer.to_data_model().unverified_data_model.as_verified_data_model()

        assert david_rules.dump() == recreated_rules.dump()
