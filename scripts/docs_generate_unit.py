import requests
from cognite.client.data_classes.units import UnitList
from datetime import date
from pathlib import Path
from itertools import groupby

UNIT_SOURCE = "https://raw.githubusercontent.com/cognitedata/units-catalog/main/versions/v1/units.json"

TODAY = date.today().strftime("%Y-%m-%d")
HEADER = f"""# Units

This document contains a list of units that are available in the Cognite Fusion platform. It was last generated {TODAY}.
For the most up-to-date list of units, please refer to the [units catalog]({UNIT_SOURCE}).

"""

QUANTITY_SECTION_TEMPL = """## {quantity}

| externalId  | name       | longName                  | symbol      | source             |
|-------------|------------|---------------------------|-------------|--------------------|
{rows}

"""

ROW_TEMPL = """| {externalId} | {name} | {longName} | {symbol} | {qudt} |"""

DESTINATION_FILE = Path(__file__).resolve().parent.parent / 'docs' / 'excel_data_modeling' / 'units.md'

def generate_units_md() -> None:
    response = requests.get(UNIT_SOURCE)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch units from {UNIT_SOURCE}")
    source = response.json()

    units = UnitList._load(source)
    doc = [HEADER]
    for quantity, unit_qunatities in groupby(sorted(units, key=lambda u: (u.quantity,u.external_id)), key=lambda u: u.quantity):
        rows = []
        for unit in unit_qunatities:
            rows.append(ROW_TEMPL.format(
                externalId=unit.external_id,
                name=unit.name,
                longName=unit.long_name,
                symbol=unit.symbol,
                qudt=f"[{unit.source_reference}]({unit.source_reference})" if unit.source_reference else ""
            ))
        doc.append(QUANTITY_SECTION_TEMPL.format(quantity=quantity, rows="\n".join(rows)))
    DESTINATION_FILE.write_text("\n".join(doc), encoding="utf-8")


if __name__ == "__main__":
    generate_units_md()
