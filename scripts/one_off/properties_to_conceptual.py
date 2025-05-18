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
from cognite.neat.core._data_model.models.conceptual import UnverifiedConceptualDataModel, UnverifiedConceptualProperty, UnverifiedConcept, UnverifiedConceptualMetadata
from cognite.neat.core._data_model.exporters import ExcelExporter


def convert_properties_to_conceptual(prop_df: pd.DataFrame, data_model_id: tuple[str, str, str]) -> UnverifiedConceptualDataModel:
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
    concepts = prop_df["type"].dropna().unique()
    concepts = [
        UnverifiedConcept(concept=class_id)
        for class_id in concepts
    ]
    properties: list[UnverifiedConceptualProperty] = []
    for class_id, class_df in prop_df.groupby("type"):
        property_ids = class_df["property"].dropna().unique()
        properties.extend([
            UnverifiedConceptualProperty(
                class_id,
                property_id,
                value_type="text",
                name=property_id,
            )
            for property_id in property_ids
        ])

    # Create the metadata
    metadata = UnverifiedConceptualMetadata(
        name="Conceptual Model",
        description="Converted from properties",
        creator=getpass.getuser(),
        space=data_model_id[0],
        external_id=data_model_id[1],
        version=data_model_id[2],
    )

    return UnverifiedConceptualDataModel(
        metadata=metadata,
        concepts=concepts,
        properties=properties,
    )
