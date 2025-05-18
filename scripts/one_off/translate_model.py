"""This script translates a conceptual model from a source language to the target language English.

The script uses the Cloud Translation APi from Google to perform the translation.

"""
from pathlib import Path
from googletrans import Translator

from cognite.neat.core._data_model.exporters import ExcelExporter
from cognite.neat.core._data_model.models import UnverifiedConceptualDataModel
from cognite.neat.core._utils.collection_ import chunker
from cognite.neat.core._utils.text import NamingStandardization
from rich import print
import json

async def translate_property_ids(input_rules: UnverifiedConceptualDataModel, output_model: Path, source_language: str, translation_file: Path, standardize: bool = True) -> None:
    """Translates the property Ids of the input model to English.

    Args:
        input_rules: The conceptual model to translate.
        output_model: A conceptual model given as a filepath to a spreadsheet.
        source_language: The source language of the input model.
        translation_file: A file with raw translations. It is used to avoid repeated API calls.
        standardize: If True, the Ids will be standardized the property and class IDs. The standardization uses
            PascalCase for the class IDs and camelCase for the property IDs. If False, the Ids will be
            translated to English without standardization.

    """
    class_renaming: dict[str, str] = {}
    if standardize:
        # Standardize the class Ids
        for concept in input_rules.concepts:
            if concept.name is None:
                continue
            new_class_id = NamingStandardization.standardize_concept_str(concept.name)
            class_renaming[concept.concept] = new_class_id
            concept.concept = new_class_id

    # Storing all translations to avoid repeated API calls
    translations: dict[str, str] = {}
    if translation_file.exists():
        translations = json.loads(translation_file.read_text(encoding="utf-8"))
        assert isinstance(translations, dict)

    translator = Translator()
    for properties in chunker(input_rules.properties, 10):
        to_translate = []
        for property_ in properties:
            if property_.name is None or property_.name in translations:
                continue
            to_translate.append(property_.name)
        if to_translate:
            translated = await translator.translate(to_translate, src=source_language, dest="en")
            for response in translated:
                translations[response.origin] = response.text
            print(f"Translated {len(to_translate)} properties.")
            translation_file.write_text(json.dumps(translations), encoding="utf-8")
        for property_ in properties:
            property_.concept = class_renaming.get(property_.concept, property_.concept)
            if property_.name is None:
                continue
            if property_.name in translations:
                property_.property_ = translations[property_.name]
            else:
                print(f"[red]Warning[/red]: {property_.name} not found in translations.")
            if standardize:
                property_.property_ = NamingStandardization.standardize_property_str(property_.property_)

    exporter = ExcelExporter(styling="maximal")
    exporter.export_to_file(input_rules.as_verified_data_model(), output_model)
    print(f"Exported {len(input_rules.properties)} properties and {len(input_rules.concepts)} classes to {output_model.as_posix()}.")
