import pytest
from cognite.client import data_modeling as dm

from cognite.neat.legacy.rules import exporters, importers
from tests.data import (
    CAPACITY_BID_CONTAINERS,
    CAPACITY_BID_JSON,
    CAPACITY_BID_MODEL,
    OSDUWELLS_MODEL,
    SCENARIO_INSTANCE_MODEL,
)


@pytest.mark.parametrize(
    "data_model", [pytest.param(m, id=m.external_id) for m in [OSDUWELLS_MODEL, SCENARIO_INSTANCE_MODEL]]
)
def test_import_export_data_model(data_model: dm.DataModel[dm.View]):
    rules = importers.DMSImporter(data_model).to_rules()

    exported = exporters.DMSExporter(rules, data_model_id=data_model.as_id()).export()

    assert exported.data_model.dump() == data_model.as_apply().dump()


def test_import_arbitrary_json_export_data_model():
    original_model = CAPACITY_BID_MODEL

    rules = importers.ArbitraryJSONImporter(CAPACITY_BID_JSON).to_rules()
    imported_model = exporters.DMSExporter(rules, data_model_id=original_model.as_id()).export()

    imported_model.data_model.name = original_model.name
    imported_model.data_model.description = original_model.description

    assert imported_model.data_model.dump() == original_model.dump()


def test_import_arbitrary_json_export_containers():
    original_model = CAPACITY_BID_MODEL

    rules = importers.ArbitraryJSONImporter(CAPACITY_BID_JSON).to_rules()
    imported_model = exporters.DMSExporter(rules, data_model_id=original_model.as_id()).export()

    imported_model.data_model.name = original_model.name
    imported_model.data_model.description = original_model.description

    original_containers = CAPACITY_BID_CONTAINERS

    assert imported_model.containers.dump() == original_containers.dump()
