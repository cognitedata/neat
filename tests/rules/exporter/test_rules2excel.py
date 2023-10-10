from cognite.neat.rules.exporter.rules2excel import RulesToExcel


def test_rules2excel(simple_rules):
    exporter = RulesToExcel(rules=simple_rules)
    exporter.generate_workbook()
    assert exporter.workbook.sheetnames == ["Metadata", "Classes", "Properties"]
    assert exporter.class_counter == len(simple_rules.classes)
    assert exporter.property_counter == len(simple_rules.properties)
