from pathlib import Path

from cognite.neat._rules.exporters import YAMLExporter
from cognite.neat._rules.importers import YAMLImporter
from cognite.neat._rules.models import DMSRules, DomainRules, InformationRules
from cognite.neat._rules.transformers import ImporterPipeline


class TestYAMLExporter:
    def test_export_import_rules(self, alice_rules: DMSRules, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(alice_rules, tmp_path / "tmp.yaml")
        importer = YAMLImporter.from_file(tmp_path / "tmp.yaml")

        recreated_rules = ImporterPipeline.verify(importer)

        assert alice_rules.dump() == recreated_rules.dump()

    def test_export_import_information_rules(self, david_rules: InformationRules, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(david_rules, tmp_path / "tmp.yaml")
        importer = YAMLImporter.from_file(tmp_path / "tmp.yaml")

        recreated_rules = ImporterPipeline.verify(importer)

        assert david_rules.dump() == recreated_rules.dump()

    def test_export_domain_rules(self, jon_rules: DomainRules, tmp_path: Path) -> None:
        exporter = YAMLExporter(files="single", output="yaml")
        exporter.export_to_file(jon_rules, tmp_path / "tmp.yaml")
        importer = YAMLImporter.from_file(tmp_path / "tmp.yaml")

        recreated_rules = ImporterPipeline.verify(importer)

        assert jon_rules.model_dump() == recreated_rules.model_dump()
