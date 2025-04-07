from pathlib import Path

from lxml import etree
from openpyxl import Workbook, load_workbook

from cognite.neat._rules.exporters import ExcelExporter
from cognite.neat._rules.models import (
    DMSRules,
    InformationRules,
)
from cognite.neat._rules.models._base_rules import RoleTypes


def compare_cells(expected: Workbook, resulted: Workbook) -> list[bool]:
    skip_rows = [header for header in ExcelExporter()._main_header_by_sheet_name.values()] + ["created", "updated"]
    comparison_results = []

    for sheet_name in expected.sheetnames:
        for row1, row2 in zip(
            expected[sheet_name].iter_rows(values_only=True),
            resulted[sheet_name].iter_rows(values_only=True),
            strict=False,
        ):
            if row1[0] in skip_rows:
                continue
            row1 = tuple("" if cell is None else cell for cell in row1)
            row2 = tuple("" if cell is None else cell for cell in row2)

            comparison_results += [row1 == row2]
    return comparison_results


def compare_data_validators(expected: Workbook, resulted: Workbook) -> list[bool]:
    comparison_results = []

    for sheet_name in expected.sheetnames:
        comparison_results += [expected[sheet_name].data_validations == resulted[sheet_name].data_validations]
    return comparison_results


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

    def test_conceptual_data_model_template(self, tmp_path: Path):
        exporter = ExcelExporter()

        expected = exporter.template(RoleTypes.information)

        template_path = tmp_path / "template.xlsx"
        exporter.template(RoleTypes.information, template_path)

        resulted = load_workbook(template_path)

        assert expected.sheetnames == resulted.sheetnames
        assert all(compare_cells(expected, resulted))
        assert all(compare_data_validators(expected, resulted))

        # There should be two data validators in the Properties sheet
        # one for Class column another one for Value Type column

        assert expected["Properties"].data_validations.count == 2
        assert resulted["Properties"].data_validations.count == 2

        assert f"<formula1>={exporter._helper_sheet_name}!A$1:A$100</formula1>" in etree.tostring(
            resulted["Properties"].data_validations.to_tree(), pretty_print=True
        ).decode("utf-8")

        assert f"<formula1>={exporter._helper_sheet_name}!B$1:B$100</formula1>" in etree.tostring(
            resulted["Properties"].data_validations.to_tree(), pretty_print=True
        ).decode("utf-8")

        assert expected["Classes"].data_validations.count == 1
        assert resulted["Classes"].data_validations.count == 1

        assert f"<formula1>={exporter._helper_sheet_name}!C$1:C$133</formula1>" in etree.tostring(
            resulted["Classes"].data_validations.to_tree(), pretty_print=True
        ).decode("utf-8")
