from pathlib import Path

import xlsxwriter

from cognite.neat.core.data_classes.transformation_rules import TransformationRules


def _column_number_to_letter(column_number: int) -> str:
    """Converts a column number to a letter"""
    dividend = column_number
    column_letter = ""
    while dividend > 0:
        modulo = (dividend - 1) % 26
        column_letter = chr(65 + modulo) + column_letter
        dividend = int((dividend - modulo) / 26)
    return column_letter


def rules2graph_template(file_path: Path, transformation_rules: TransformationRules, add_drop_down_list: bool = False):
    """Converts a transformation rules to a Excel template for knowledge graph data entry"""

    workbook = xlsxwriter.Workbook(file_path)

    header_format = workbook.add_format(
        {
            "border": 1,
            "bg_color": "#C6EFCE",
            "bold": True,
            "text_wrap": True,
            "valign": "vcenter",
            "indent": 1,
            "font_size": 16,
            "font_name": "Helvetica",
        }
    )

    sheets = {}

    for class_, properties in transformation_rules.get_classes_with_properties().items():
        sheets[class_] = workbook.add_worksheet(class_)
        sheets[class_].write(0, 0, "identifier", header_format)

        print(50 * "-")
        print(class_)
        for i in range(len(properties) + 1):
            print(f"{_column_number_to_letter(i+1)}:{_column_number_to_letter(i+1)}")
            sheets[class_].set_column(f"{_column_number_to_letter(i+1)}:{_column_number_to_letter(i+1)}", 30)

        processed_properties = set()
        subtract = 0

        for i, property_ in enumerate(properties):
            if property_.property_name in processed_properties:
                subtract += 1
                continue

            processed_properties.add(property_.property_name)
            sheets[class_].write(0, i + 1 - subtract, property_.property_name, header_format)

            if property_.property_type == "ObjectProperty" and add_drop_down_list:
                # here add drop down list
                pass

    workbook.close()
