import inspect
from datetime import date
from pathlib import Path
from types import UnionType
from typing import get_args, get_origin
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from cognite.neat.v0.core._data_model.models import PhysicalDataModel, ConceptualDataModel
from cognite.neat.v0.core._data_model.models._base_verified import BaseVerifiedDataModel

DMS_REFERENCE_MD = Path(__file__).resolve().parent.parent / 'docs' / 'excel_data_modeling' / 'physical' / 'reference.md'
INFO_REFERENCE_MD = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "excel_data_modeling"
    / "conceptual"
    / "reference.md"
)
TODAY = date.today().strftime("%Y-%m-%d")

HEADER = """# {name_title} Reference

This document is a reference for the {name} data model. It was last generated {today}.

The {name} data model has the following sheets:
{sheets}
"""

SHEET_TEMPLATE = """## {sheet_name} Sheet

{description}

| {col_or_field} | Description | Mandatory |
|----------------|-------------|-----------|
{rows}
"""

ROW_TEMPLATE = """| {column_name} | {description} | {mandatory} |"""


def generate_reference(
    name: str, rules: type[BaseVerifiedDataModel], target_file: Path
) -> None:
    sheet_overview: list[str] = []
    sheet_list: list[str] = []
    for field_name, field_ in rules.model_fields.items():
        if field_name == "validators_to_skip":
            continue
        sheet_name = field_.alias or field_name
        optional = ""
        if field_.default is None:
            optional = " (optional)"
        sheet_overview.append(f"- {sheet_name}{optional}: {field_.description}")

        if field_name == "prefixes":
            # Don't know how to handle this yet
            continue

        field_cls = get_field_cls_type(field_)
        rows: list[str] = []
        for column_id, column in field_cls.model_fields.items():
            if column_id == "validators_to_skip":
                continue
            column_name = column.alias or column_id
            # Special case for space prefix
            column_name = {"prefix":"space"}.get(column_name, column_name)
            is_mandatory = column.default is not None
            rows.append(ROW_TEMPLATE.format(
                column_name=column_name,
                description=column.description,
                mandatory="Yes" if is_mandatory else "No"
            ))
        sheet_list.append(SHEET_TEMPLATE.format(
            sheet_name=sheet_name,
            description=field_.description,
            col_or_field="Field" if field_name == "metadata" else "Column Name",
            rows="\n".join(rows)
        ))

    doc = [HEADER.format(
        name=name, today=TODAY, name_title=name.title(),
                         sheets="\n".join(sheet_overview))] + sheet_list

    target_file.write_text("\n".join(doc), encoding="utf-8")


def get_field_cls_type(field: FieldInfo) -> type[BaseModel]:
    if inspect.isclass(field.annotation) and issubclass(field.annotation, BaseModel):
        return field.annotation
    origin = get_origin(field.annotation)
    cls_ = field.annotation
    args = get_args(cls_)
    if origin is UnionType and len(args) == 2 and args[1] == type(None):
        cls_ = args[0]
        origin = get_origin(cls_)
        args = get_args(cls_)

    is_generic = origin is not cls_

    if is_generic:
        if len(args) == 1 and issubclass(args[0], BaseModel):
            return args[0]
    raise NotImplementedError(f"Failed to get field class type {field.annotation}")


if __name__ == "__main__":
    generate_reference("physical", PhysicalDataModel, DMS_REFERENCE_MD)
    generate_reference("conceptual", ConceptualDataModel, INFO_REFERENCE_MD)
