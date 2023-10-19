from pathlib import Path
from typing import cast

from openpyxl import Workbook
from openpyxl.cell import Cell
from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side

from cognite.neat.rules.models import Class, Metadata, Property, TransformationRules
from cognite.neat.rules.parser import RawTables, raw_tables_to_rules_dict


class RulesToExcel:
    """Class for exporting transformation rules object to excel file."""

    def __init__(self, rules: TransformationRules | RawTables):
        if rules.__class__.__name__ == RawTables.__name__:
            self.rules = self.tables_to_rules(rules=cast(RawTables, rules))
        else:
            self.rules = cast(TransformationRules, rules)

        self.workbook = Workbook()
        self.class_counter = 0
        self.property_counter = 0

    @classmethod
    def export_rules_to_file(cls, rules: TransformationRules | RawTables, file_path: Path):
        """Generates workbook from transformation rules and saves it to file."""
        instance = cls(rules=rules)
        instance.generate_workbook()
        instance.save_to_file(file_path=file_path)

    def generate_workbook(self):
        """Generates workbook from transformation rules."""
        self.workbook = Workbook()
        # Remove default sheet named "Sheet"
        self.workbook.remove(self.workbook["Sheet"])
        # Serialize the rules to the excel file

        # map rules metadata to excel
        metadata = self.rules.metadata
        metadata_sheet = self.workbook.create_sheet("Metadata")

        # add each metadata property to the sheet as a row

        metadata_sheet.append(["title", metadata.title])
        metadata_sheet.append(["description", metadata.description])
        metadata_sheet.append(["version", metadata.version])
        metadata_sheet.append(["creator", ",".join(metadata.creator)])
        metadata_sheet.append(["created", metadata.created])
        metadata_sheet.append(["dataModelName", metadata.data_model_name])
        metadata_sheet.append(["cdfSpaceName", metadata.cdf_space_name])
        metadata_sheet.append(["prefix", metadata.prefix])
        metadata_sheet.append(["namespace", metadata.namespace])

        # map classes to excel sheet named "Classes" and add each class as a row
        classes_sheet = self.workbook.create_sheet("Classes")

        classes_sheet.append(["Solution model", "", ""])
        classes_sheet.merge_cells("A1:C1")
        classes_sheet.append(["Class", "Description", "Parent Class"])  # A  # B  # C

        for class_ in self.rules.classes.values():
            self.class_counter += 1
            classes_sheet.append([class_.class_id, class_.description, class_.parent_class])

        # map properties to excel sheet named "Properties" and add each property as a row
        properties_sheet = self.workbook.create_sheet("Properties")
        properties_sheet.append(
            [
                "Solution model",  # A
                "",  # B
                "",  # C
                "",  # D
                "",  # E
                "",  # F
                "Solution classic CDF resources",  # G
                "",  # H
                "",  # I
                "",  # J
                "",  # K
                "",  # L
                "Transformation rules",  # M
                "",  # N
            ]
        )
        properties_sheet.merge_cells("A1:F1")
        properties_sheet.merge_cells("G1:L1")
        properties_sheet.merge_cells("M1:N1")
        properties_sheet.append(
            [
                "Class",  # A
                "Property",  # B
                "Description",  # C
                "Type",  # D
                "Min Count",  # E
                "Max Count",  # F
                "Resource Type",  # G
                "Resource Type Property",  # H
                "Relationship Source Type",  # I
                "Relationship Target Type",  # J
                "Relationship Label",  # K
                "Relationship ExternalID Rule",  # L
                "Rule Type",  # M
                "Rule",  # N
            ]
        )

        for property_ in self.rules.properties.values():
            self.property_counter += 1
            properties_sheet.append(
                [
                    property_.class_id,  # A
                    property_.property_id,  # B
                    property_.description,  # C
                    property_.expected_value_type,  # D
                    property_.min_count,  # E
                    property_.max_count,  # F
                    ",".join(property_.cdf_resource_type) if property_.cdf_resource_type else "",  # G
                    ",".join(property_.resource_type_property) if property_.resource_type_property else "",  # H
                    property_.source_type,  # I
                    property_.target_type,  # J
                    property_.label,  # K
                    property_.relationship_external_id_rule,  # L
                    property_.rule_type,  # M
                    property_.rule,  # N
                ]
            )
        self.set_header_style()

    def save_to_file(self, file_path: Path):
        self.workbook.save(file_path)
        self.workbook.close()

    def set_header_style(self):
        """Sets the header style for all sheets in the self.workbook"""
        style = NamedStyle(name="header style")
        style.font = Font(bold=True, size=16)
        side = Side(style="thin", color="000000")
        style.border = Border(left=side, right=side, top=side, bottom=side)
        self.workbook.add_named_style(style)

        for sheet in self.workbook.sheetnames:
            if sheet == "Metadata":
                continue
            if sheet == "Classes" or sheet == "Properties":
                sheet_obj = self.workbook[sheet]
                if sheet == "Classes":
                    sheet_obj.freeze_panes = "A3"
                else:
                    sheet_obj.freeze_panes = "D3"

                for cell in sheet_obj[1]:
                    cell = cast(Cell, cell)  # type: ignore[index]
                    cell.style = style
                    cell.fill = PatternFill("solid", start_color="3fd968")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                for cell in sheet_obj[2]:
                    cell = cast(Cell, cell)  # type: ignore[index]
                    cell.style = style
                    cell.fill = PatternFill("solid", start_color="d5dbd5")
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    adjusted_width = (len(str(cell.value)) + 5) * 1.2
                    self.workbook[sheet].column_dimensions[cell.column_letter].width = adjusted_width

    @staticmethod
    def tables_to_rules(rules: RawTables) -> TransformationRules:
        rules = raw_tables_to_rules_dict(rules)
        args = {
            "metadata": Metadata.model_construct(**rules["metadata"]),
            "classes": {class_: Class.model_construct(**definition) for class_, definition in rules["classes"].items()},
            "properties": {
                property_: Property.model_construct(**definition)
                for property_, definition in rules["properties"].items()
            },
            "prefixes": rules["prefixes"],
        }

        return TransformationRules.model_construct(**args)
