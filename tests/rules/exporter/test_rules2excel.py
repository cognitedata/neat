from cognite.neat.rules.exporter import ExcelExporter


def test_rules2excel(simple_rules):
    exporter = ExcelExporter(rules=simple_rules, filepath=None)

    assert exporter.data.sheetnames == ["Metadata", "Classes", "Properties", "Prefixes"]
    assert exporter.class_counter == len(simple_rules.classes)
    assert exporter.property_counter == len(simple_rules.properties)
