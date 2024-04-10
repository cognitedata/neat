from cognite.neat.rules import importers


def test_owl_importer():
    rules, _ = importers.OWLImporter(owl_filepath="https://data.nobelprize.org/terms.rdf").to_rules()

    assert len(rules.classes) == 11
    assert len(rules.properties) == 16
