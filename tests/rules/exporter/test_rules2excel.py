from pathlib import Path

from cognite.neat.rules.exporter import ExcelExporter
from cognite.neat.rules.importer import ExcelImporter


def test_rules2excel(simple_rules, tmp_path: Path) -> None:
    file = tmp_path / "rules.xlsx"

    ExcelExporter(rules=simple_rules).export_to_file(filepath=file)

    importer = ExcelImporter(filepath=file).to_rules()

    assert len(importer.classes) == len(simple_rules.classes)
    assert len(importer.properties) == len(simple_rules.properties)
    assert importer.properties.model_dump() == simple_rules.properties.model_dump()
