"""This script translates a conceptual model from a source language to the target language English.

The script uses the Cloud Translation APi from Google to perform the translation.

"""
from pathlib import Path
from googletrans import Translator
from cognite.neat._rules.importers import ExcelImporter
from cognite.neat._rules.exporters import ExcelExporter
from cognite.neat._rules.models import InformationInputRules
from cognite.neat._utils.collection_ import chunker
from cognite.neat._utils.text import NamingStandardization
from rich import print
import json

async def translate_property_ids(input_model: Path, output_model: Path, source_language: str, translation_file: Path, standardize: bool = True) -> None:
    """Translates the property Ids of the input model to English.

    Args:
        input_model: A conceptual model given as a filepath to a spreadsheet.
        output_model: A conceptual model given as a filepath to a spreadsheet.
        source_language: The source language of the input model.
        translation_file: A file with raw translations. It is used to avoid repeated API calls.
        standardize: If True, the Ids will be standardized the property and class IDs. The standardization uses
            PascalCase for the class IDs and camelCase for the property IDs. If False, the Ids will be
            translated to English without standardization.

    """
    importer = ExcelImporter(input_model)
    input_rules = importer.to_rules().rules
    if input_rules is None:
        raise RuntimeError(f"Failed to load rules from {input_model}.")
    assert isinstance(input_rules, InformationInputRules)

    class_renaming: dict[str, str] = {}
    if standardize:
        # Standardize the class Ids
        for class_ in input_rules.classes:
            if class_.name is None:
                continue
            new_class_id = NamingStandardization.standardize_class_str(class_.name)
            class_renaming[class_.class_] = new_class_id
            class_.class_ = new_class_id

    # Storing all translations to avoid repeated API calls
    translations: dict[str, str] = {}
    if translation_file.exists():
        translations = json.loads(translation_file.read_text())
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
        for property_ in properties:
            property_.class_ = class_renaming.get(property_.class_, property_.class_)
            if property_.name is None:
                continue
            if property_.name in translations:
                property_.property_ = translations[property_.name]
            else:
                print(f"[red]Warning[/red]: {property_.name} not found in translations.")
            if standardize:
                property_.property_ = NamingStandardization.standardize_property_str(property_.property_)

    translation_file.write_text(json.dumps(translations))

    exporter = ExcelExporter(styling="maximal")
    exporter.export_to_file(input_rules.as_verified_rules(), output_model)
    print(f"Exported {len(input_rules.properties)} properties and {len(input_rules.classes)} classes to {output_model.as_posix()}.")
