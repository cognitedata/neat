"""This script translates a conceptual model from a source language to the target language English.

The script uses the Cloud Translation APi from Google to perform the translation.

"""
from pathlib import Path


def translate_property_ids(input_model: Path, output_model: Path, source_language: str, standardize: bool = True) -> None:
    """Translates the property Ids of the input model to English.

    Args:
        input_model: A conceptual model given as a filepath to a spreadsheet.
        output_model: A conceptual model given as a filepath to a spreadsheet.
        source_language: The source language of the input model.
        standardize: If True, the Ids will be standardized the property and class IDs. The standardization uses
            PascalCase for the class IDs and camelCase for the property IDs. If False, the Ids will be
            translated to English without standardization.

    """
    raise NotImplementedError
