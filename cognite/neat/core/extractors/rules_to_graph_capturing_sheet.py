import logging
import uuid
import warnings
from pathlib import Path

import xlsxwriter

from cognite.neat.core.data_classes.transformation_rules import TransformationRules
from cognite.neat.core.extractors.rules_to_graphql import repair_name as to_graphql_name


def _get_column(column_number: int) -> str:
    """Converts a column number to a letter"""
    dividend = column_number
    column_letter = ""
    while dividend > 0:
        modulo = (dividend - 1) % 26
        column_letter = chr(65 + modulo) + column_letter
        dividend = int((dividend - modulo) / 26)
    return column_letter


def _get_header_style(**kwargs):
    """Return the header style"""
    header_cfg = {
        "border": kwargs.get("border", 1),
        "bg_color": kwargs.get("bg_color", "#2FB5F2"),
        "bold": kwargs.get("bold", True),
        "text_wrap": kwargs.get("text_wrap", False),
        "valign": kwargs.get("valign", "vcenter"),
        "indent": kwargs.get("indent", 1),
        "font_size": kwargs.get("font_size", 16),
        "font_name": kwargs.get("font_name", "Helvetica"),
    }

    identifier_header_cfg = header_cfg.copy()
    identifier_header_cfg["bg_color"] = "#FFB202"

    return header_cfg, identifier_header_cfg


def _add_uuid_identifiers(sheets, sheet_name, no_rows):
    """Adds UUID-based auto identifier to a sheet"""
    for i in range(no_rows):
        fixed_name = to_graphql_name(sheet_name, "class", True)
        sheets[sheet_name].write_formula(f"A{i+2}", f'=IF(ISBLANK(B{i+2}), "","{fixed_name}-{uuid.uuid4()}")')


def _add_index_identifiers(sheets, sheet_name, no_rows):
    """Adds index-based auto identifier to a sheet"""
    for i in range(no_rows):
        fixed_name = to_graphql_name(sheet_name, "class", True)
        sheets[sheet_name].write_formula(f"A{i+2}", f'=IF(ISBLANK(B{i+2}), "","{fixed_name}-{i+1}")')


def _set_column_width(sheet, no_columns, width):
    """Sets the width of all columns in a sheet"""
    for i in range(no_columns + 1):
        sheet.set_column(i, i, width)


def _add_drop_down_list(sheets, sheet_name, column, no_rows, value_sheet, value_column):
    """Adds a drop down list to a column"""
    logging.info(f"Adding drop down list to <{sheet_name}!{column}> with values from <{value_sheet}!{value_column}>")
    for i in range(no_rows):
        sheets[sheet_name].data_validation(
            f"{column}{i+2}",
            {
                "validate": "list",
                "source": f"={value_sheet}!{value_column}2:{value_column}{no_rows}",
            },
        )


def rules2graph_capturing_sheet(
    file_path: Path,
    transformation_rules: TransformationRules,
    no_rows: int = 1000,
    use_index_id: bool = True,
    use_uuid_id: bool = False,
    add_drop_down_list: bool = True,
    **kwargs,
):
    """Converts a TransformationRules object to a graph capturing sheet

    Parameters
    ----------
    file_path : Path
        File path to save the sheet to
    transformation_rules : TransformationRules
        The TransformationRules object to convert to the graph capturing sheet
    use_uuid_id : bool, optional
        Use UUID-based for automatic identifiers, by default False
    use_index_id : bool, optional
        Use Index-based for automatic identifiers, by default True
    no_rows : int, optional
        Number of rows for processing, by default 1000
    add_drop_down_list : bool, optional
        Add drop down selection for columns that contain linking properties, by default True
    **kwargs : dict
        Additional arguments to pass to the function dealing with header style

    Notes
    -----
    no_rows should be set to maximum expected number of instances of any of the classes.
    By default it is set to 1000, increase it accordingly if you have more instances.

    """

    workbook = xlsxwriter.Workbook(file_path)
    header_format = workbook.add_format(_get_header_style()[0])
    identifier_format = workbook.add_format(_get_header_style()[1])
    sheets = {}

    for class_, properties in transformation_rules.get_classes_with_properties().items():
        sheets[class_] = workbook.add_worksheet(class_)
        sheets[class_].write(0, 0, "identifier", identifier_format)
        _set_column_width(sheets[class_], len(properties), kwargs.get("column_width", 30))

        if use_index_id:  # default, easy to read
            logging.info("Configuring index-based automatic identifiers")
            _add_index_identifiers(sheets, class_, no_rows)
        elif use_uuid_id:
            logging.info("Configuring UUID-based automatic identifiers")
            _add_uuid_identifiers(sheets, class_, no_rows)
        else:
            logging.info("No automatic identifiers used")

        processed_properties = set()
        subtract = 0

        for i, property_ in enumerate(properties):
            if property_.property_name in processed_properties:
                subtract += 1
                logging.warn(f"Property {property_.property_name} being redefined... skipping!")
                warnings.warn(f"Property {property_.property_name} being redefined... skipping!", stacklevel=2)
                continue

            processed_properties.add(property_.property_name)
            sheets[class_].write(0, i + 1 - subtract, property_.property_name, header_format)

            if property_.property_type == "ObjectProperty" and add_drop_down_list:
                _add_drop_down_list(
                    sheets,
                    class_,
                    _get_column(i + 1 - subtract + 1),
                    no_rows,
                    property_.expected_value_type,
                    "A",
                )

    workbook.close()
    logging.info(f"Knowledge graph capturing sheet generated and stored {file_path}!")
