from cognite.neat.rules.exporters import ExcelExporter
from cognite.neat.rules.models._rules import DMSRules, DomainRules, InformationRules


class TestExcelExporter:
    def test_export_dms_rules(self, alice_rules: DMSRules):
        exporter = ExcelExporter(styling="maximal")
        workbook = exporter.export(alice_rules)
        assert "Metadata" in workbook.sheetnames
        assert "Containers" in workbook.sheetnames
        assert "Views" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

    def test_export_information_rules(self, david_rules: InformationRules):
        exporter = ExcelExporter()
        workbook = exporter.export(david_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Classes" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

    def test_export_domain_rules(self, jon_rules: DomainRules):
        exporter = ExcelExporter()
        workbook = exporter.export(jon_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

    def test_export_domain_rules_emma(self, emma_rules: DomainRules):
        exporter = ExcelExporter()
        workbook = exporter.export(emma_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames
        assert "Classes" in workbook.sheetnames

    def test_export_dms_rules_alice_reference(self, alice_rules: DMSRules) -> None:
        exporter = ExcelExporter(styling="maximal")
        # Make a copy of the rules to avoid changing the original
        alice_copy = alice_rules.copy()
        alice_copy.is_reference = True
        workbook = exporter.export(alice_copy)

        assert "Metadata" in workbook.sheetnames
        assert "Containers" in workbook.sheetnames
        assert "Views" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

        assert "ReferenceProperties" in workbook.sheetnames
        assert "ReferenceContainers" in workbook.sheetnames
        assert "ReferenceViews" in workbook.sheetnames
