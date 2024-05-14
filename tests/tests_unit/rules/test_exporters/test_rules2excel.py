import pytest

from cognite.neat.rules.exporters import ExcelExporter
from cognite.neat.rules.models import DMSRules, DomainRules, InformationRules


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
        exporter = ExcelExporter(styling="maximal", dump_as="reference")
        workbook = exporter.export(alice_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Containers" in workbook.sheetnames
        assert "Views" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

        assert "RefProperties" in workbook.sheetnames
        assert "RefContainers" in workbook.sheetnames
        assert "RefViews" in workbook.sheetnames

        rows = next((rows for rows in workbook["RefProperties"].columns if rows[1].value == "Reference"), None)
        assert rows is not None, "Reference column not found in RefProperties sheet"

        # Two first rows are headers
        reference_count = sum(1 for row in rows[2:] if row.value is not None)
        assert reference_count >= len(alice_rules.properties)

        rows = next((rows for rows in workbook["RefContainers"].columns if rows[1].value == "Reference"), None)
        assert rows is not None, "Reference column not found in RefContainers sheet"
        assert sum(1 for row in rows[2:] if row.value is not None) >= len(alice_rules.containers)

        rows = next((rows for rows in workbook["RefViews"].columns if rows[1].value == "Reference"), None)
        assert rows is not None, "Reference column not found in RefViews sheet"
        assert sum(1 for row in rows[2:] if row.value is not None) >= len(alice_rules.views)

    @pytest.mark.parametrize(
        "dump_as, expected_sheet_names",
        [
            ("user", {"Metadata", "Classes", "Properties", "RefMetadata", "RefClasses", "RefProperties"}),
            (
                "last",
                {
                    "Metadata",
                    "Classes",
                    "Properties",
                    "LastClasses",
                    "LastProperties",
                    "RefMetadata",
                    "RefClasses",
                    "RefProperties",
                },
            ),
        ],
    )
    def test_export_olav_rules_dump_as(
        self, dump_as: ExcelExporter.DumpOptions, expected_sheet_names: set[str], olav_rules: InformationRules
    ) -> None:
        exporter = ExcelExporter(styling="maximal", dump_as=dump_as)
        assert olav_rules.reference is not None, "Olav rules are expected to have a reference set"
        # Make a copy of the rules to avoid changing the original
        olav_copy = olav_rules.model_copy(deep=True)

        workbook = exporter.export(olav_copy)

        missing = expected_sheet_names - set(workbook.sheetnames)
        assert not missing, f"Missing sheets: {missing}"
        extra = set(workbook.sheetnames) - expected_sheet_names
        assert not extra, f"Extra sheets: {extra}"
