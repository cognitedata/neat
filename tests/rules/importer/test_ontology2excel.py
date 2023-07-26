def test_owl2transformation_rules(owl_based_rules):
    raw_tables = owl_based_rules
    assert raw_tables.Metadata.iloc[0, 1] == "https://kg.cognite.ai/wind/"
    assert len(set(raw_tables.Classes.Class.values)) == 68
