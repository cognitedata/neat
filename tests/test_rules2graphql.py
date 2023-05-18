from cognite.neat.core.extractors.rules_to_graphql import get_invalid_names, repair_name, rules2graphql_schema


def test_rules2graphql(simple_rules, grid_graphql_schema):
    assert rules2graphql_schema(simple_rules) == grid_graphql_schema


def test_get_invalid_names():
    assert get_invalid_names({"wind-speed", "83windSpeed", "windSpeed"}) == {"wind-speed", "83windSpeed"}


def test_repair_name():
    assert repair_name("wind-speed", "property") == "windspeed"
    assert repair_name("Wind.Speed", "property", True) == "windSpeed"
    assert repair_name("windSpeed", "class", True) == "WindSpeed"
    assert repair_name("22windSpeed", "class") == "_22windSpeed"
