from pathlib import Path

from cognite.neat.core._rules.exporters import YAMLExporter
from cognite.neat.core._rules.importers import YAMLImporter
from cognite.neat.core._rules.models import DMSRules, InformationRules


class TestYAMLExporter:
    def test_export_import_rules(self, alice_rules: DMSRules, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(alice_rules, tmp_path / "tmp.yaml")
        importer = YAMLImporter.from_file(tmp_path / "tmp.yaml")

        recreated_rules = importer.to_rules().rules.as_verified_rules()

        assert alice_rules.dump() == recreated_rules.dump()

    def test_export_import_information_rules(self, david_rules: InformationRules, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(david_rules, tmp_path / "tmp.yaml")
        importer = YAMLImporter.from_file(tmp_path / "tmp.yaml")

        recreated_rules = importer.to_rules().rules.as_verified_rules()

        assert david_rules.dump() == recreated_rules.dump()
