from pathlib import Path

from cognite.neat.rules.exporters import YAMLExporter
from cognite.neat.rules.importers import YAMLImporter
from cognite.neat.rules.models._rules import DMSRules


class TestYAMLExporter:
    def test_export_import_rules(self, alice_rules: DMSRules, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="multiple", output="yaml")
        exporter.export_to_file(tmp_path, alice_rules)
        importer = YAMLImporter.from_directory(tmp_path)

        recreated_rules = importer.to_rules("raise")

        assert alice_rules == recreated_rules
