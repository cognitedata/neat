import pytest

from cognite.neat.rules.exceptions import EntitiesContainNonDMSCompliantCharacters
from cognite.neat.rules.exporter._rules2dms import DataModel


def test_rules2dms(simple_rules):
    data_model = DataModel.from_rules(rules=simple_rules)

    assert len(data_model.containers) == 4
    assert len(data_model.views) == 4
    assert list(data_model.views.keys()) == ["CountryGroup", "Country", "PriceArea", "PriceAreaConnection"]
    assert list(data_model.containers.keys()) == ["CountryGroup", "Country", "PriceArea", "PriceAreaConnection"]
    assert data_model.version == "0_1"
    assert data_model.space == "playground"
    assert data_model.external_id == "neat"


def test_raise_error10(transformation_rules):
    with pytest.raises(EntitiesContainNonDMSCompliantCharacters):
        _ = DataModel.from_rules(rules=transformation_rules)
