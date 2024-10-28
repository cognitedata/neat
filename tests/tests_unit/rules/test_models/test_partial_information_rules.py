from cognite.neat._rules import importers
from cognite.neat._rules.models import InformationRules
from cognite.neat._rules.transformers import ImporterPipeline
from tests.config import PARTIAL_MODEL_TEST_DATA


def test_partial_to_complete_mode():
    rules1 = ImporterPipeline.verify(importers.ExcelImporter(PARTIAL_MODEL_TEST_DATA / "part1.xlsx"))
    rules2 = ImporterPipeline.verify(importers.OWLImporter.from_file(PARTIAL_MODEL_TEST_DATA / "part2.ttl"))
    rules3 = ImporterPipeline.verify(importers.YAMLImporter.from_file(PARTIAL_MODEL_TEST_DATA / "part3.yaml"))

    rules1.classes += rules2.classes + rules3.classes
    rules1.properties += rules2.properties + rules3.properties
    rules1.metadata.schema_ = "complete"
    rules1.metadata.data_model_type = "enterprise"

    rules_merged = InformationRules(**rules1.model_dump())

    rules_complete = ImporterPipeline.verify(importers.ExcelImporter(PARTIAL_MODEL_TEST_DATA / "complete.xlsx"))

    assert {f"{prop.class_.id} - {prop.property_} - {prop.value_type}" for prop in rules_complete.properties} == {
        f"{prop.class_.id} - {prop.property_} - {prop.value_type}" for prop in rules_merged.properties
    }
    assert {class_.class_ for class_ in rules_complete.classes} == {class_.class_ for class_ in rules_merged.classes}
    assert rules_complete.metadata.model_dump() == rules_merged.metadata.model_dump()
