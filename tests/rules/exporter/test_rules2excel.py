from cognite.neat.rules.exporter import ExcelExporter
import tempfile
from cognite.neat.rules.importer import ExcelImporter


def test_rules2excel(simple_rules):
    file = tempfile.NamedTemporaryFile(suffix=".xlsx")

    exporter = ExcelExporter(rules=simple_rules, filepath=file).export()

    importer = ExcelImporter(filepath=file).to_rules()

    assert len(importer.classes) == len(simple_rules.classes)
    assert len(importer.properties) == len(simple_rules.properties)    
    assert importer.properties.model_dump() == simple_rules.properties.model_dump()