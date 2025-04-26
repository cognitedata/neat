"""This script converts a spreadsheet of an ill-formed model to a conceptual model.

The ill-formed model is organized as follows:

The classes names are in the header of column D-M.
The first row contains the word 'Property'.
The following rows contains the properties for each class.

In addition, there should be a shared based class defined in the same way in the B-column.

For example, the first rows of the spreadsheet looks like this:

```markdown
| common       | Pump         | HeatExchanger | StorageTank   | ... |
|--------------|--------------|---------------|---------------|-----|
| Property     | Property     | Property      | Property      | ... |
| externalId   | externalId   | externalId    | externalId    | ... |
| name         | name         | name          | name          | ... |
| description  | description  | description   | description   | ... |
| ...          | ...          | ...           | ...           | ... |
```
"""
from pathlib import Path
import pandas as pd
# from cognite.neat._rules.models.information import InformationInputClass, InformationInputMetadata, InformationInputProperty, InformationInputRules


def convert_tabular_class_property_definition_to_conceptual(input_file: Path, output_file: Path, sheet_name: str, classes: list[str], base_class: str | None = None, skip_rows: int | None = None) -> None:
    """
    Convert an ill-formed model to a conceptual model.

    Args:
        input_file (Path): Path to the input file (ill-formed model).
        output_file (Path): Path to the output file (conceptual model).
        sheet_name (str): Name of the sheet in the input file.
        classes (list[str]): List of class names to convert, expected to the column headers.
        base_class (str | None): Name of the base class, if any.
        skip_rows (int | None): Number of rows to skip at after the header.
    """
    # Read the input file
    df = pd.read_excel(input_file, sheet_name=sheet_name)

    if skip_rows:
        df = df.iloc[skip_rows:]

    properties_by_class: dict[str, list[str]] = {}
    base_property_set: set[str] = set()
    if base_class:
        if base_class not in df.columns:
            raise ValueError(f"Base class '{base_class}' not found in classes list.")
        properties_by_class[base_class] = df[base_class].dropna().drop_duplicates(keep="first").tolist()
        base_property_set = set(properties_by_class[base_class])

    for class_name in classes:
        if class_name not in df.columns:
            raise ValueError(f"Class '{class_name}' not found in classes list.")
        properties_by_class[class_name] = [prop for prop in df[class_name].dropna().drop_duplicates(keep="first").tolist() if prop not in base_property_set]

