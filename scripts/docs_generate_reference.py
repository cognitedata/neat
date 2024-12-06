from datetime import date
from pathlib import Path

from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models._base_rules import BaseRules

DMS_REFERENCE_MD = Path(__file__).resolve().parent.parent / 'docs' / 'excel_data_modeling' / 'physical' / 'reference.md'
INFO_REFERENCE_MD = Path(__file__).resolve().parent.parent / 'docs' / 'excel_data_modeling' / 'logical' / 'reference.md'
TODAY = date.today().strftime("%Y-%m-%d")

HEADER = """# {name_title} Reference

This document is a reference for the {name} data model. It was last generated {today}.

The {name} data model has the following sheets:
{sheets}
"""


def generate_reference(name: str, rules: type[BaseRules], target_file: Path) -> None:
    sheet_list: list[str] = []
    for field_name, field_ in rules.model_fields.items():
        if field_name == "validators_to_skip":
            continue
        optional = ""
        if field_.default is None:
            optional = " (optional)"
        sheet_list.append(f"- {field_.alias or field_name}{optional}: {field_.description}")

    doc = [HEADER.format(
        name=name, today=TODAY, name_title=name.title(),
                         sheets="\n".join(sheet_list))]

    target_file.write_text("\n".join(doc), encoding="utf-8")


if __name__ == "__main__":
    generate_reference("physical", DMSRules, DMS_REFERENCE_MD)
    generate_reference("logical", InformationRules, INFO_REFERENCE_MD)



