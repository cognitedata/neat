from cognite.neat.rules import importers
from cognite.neat.rules.models import InformationRules
from tests.config import PARTIAL_MODEL_TEST_DATA


def test_partial_to_complete_mode():
    rules1, _ = importers.ExcelImporter(PARTIAL_MODEL_TEST_DATA / "part1.xlsx").to_rules()
    rules2, _ = importers.OWLImporter(PARTIAL_MODEL_TEST_DATA / "part2.ttl").to_rules()
    rules3, _ = importers.YAMLImporter.from_file(PARTIAL_MODEL_TEST_DATA / "part3.yaml").to_rules()

    rules1.classes.data += rules2.classes.data + rules3.classes.data
    rules1.properties.data += rules2.properties.data + rules3.properties.data
    rules1.metadata.schema_ = "complete"

    rules_merged = InformationRules(**rules1.model_dump())

    rules_complete, _ = importers.ExcelImporter(PARTIAL_MODEL_TEST_DATA / "complete.xlsx").to_rules()

    assert {f"{prop.class_.id} - {prop.property_} - {prop.value_type}" for prop in rules_complete.properties} == {
        f"{prop.class_.id} - {prop.property_} - {prop.value_type}" for prop in rules_merged.properties
    }
    assert {class_.class_ for class_ in rules_complete.classes} == {class_.class_ for class_ in rules_merged.classes}
    assert rules_complete.metadata.model_dump() == rules_merged.metadata.model_dump()
