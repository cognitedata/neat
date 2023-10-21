from cognite.neat.rules.exporter.rules2excel import ExcelExporter


def test_rules2excel(simple_rules):
    exporter = ExcelExporter(rules=simple_rules)
    exporter.generate_workbook()
    assert exporter.data.sheetnames == ["Metadata", "Classes", "Properties"]
    assert exporter.class_counter == len(simple_rules.classes)
    assert exporter.property_counter == len(simple_rules.properties)
