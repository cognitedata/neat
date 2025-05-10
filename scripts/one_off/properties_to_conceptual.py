"""This script converts the output of the following to a conceptual model:

```python

neat = NeatSession()

neat.read...

prop_df = neat._explore.properties()

convert_properties_to_conceptual(prop_df.to_dict(orient="records"), "output.xlsx")

"""

import getpass
from pathlib import Path
import pandas as pd
from cognite.neat.core._rules.models.information import InformationInputClass, InformationInputMetadata, InformationInputProperty, InformationInputRules
from cognite.neat.core._rules.exporters import ExcelExporter


def convert_properties_to_conceptual(prop_df: pd.DataFrame, data_model_id: tuple[str, str, str]) -> InformationInputRules:
    """Convert a list of properties to a conceptual model.

    Args:
        prop_df (pd.DataFrame): List of properties to convert. Assumed to have
            the columns 'type' and 'property'.
        data_model_id (tuple[str, str, str]): Tuple containing the space, external_id, version.

    Returns:
        InformationInputRules: The conceptual model.
    """
    if {"property", "type"} - set(prop_df.columns):
        raise ValueError("Input DataFrame must contain 'property' and 'type' columns.")
    # Create the conceptual model
    classes = prop_df["type"].dropna().unique()
    classes = [
        InformationInputClass(class_=class_id)
        for class_id in classes
    ]
    properties: list[InformationInputProperty] = []
    for class_id, class_df in prop_df.groupby("type"):
        property_ids = class_df["property"].dropna().unique()
        properties.extend([
            InformationInputProperty(
                class_id,
                property_id,
                value_type="text",
                name=property_id,
            )
            for property_id in property_ids
        ])

    # Create the metadata
    metadata = InformationInputMetadata(
        name="Conceptual Model",
        description="Converted from properties",
        creator=getpass.getuser(),
        space=data_model_id[0],
        external_id=data_model_id[1],
        version=data_model_id[2],
    )

    model = InformationInputRules(
        metadata=metadata,
        classes=classes,
        properties=properties,
    )
    return model
