import pytest
from cognite.client import data_modeling as dm

from cognite.neat.rules import exporter, importer
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
    rules = importer.DMSImporter(data_model).to_rules()

    exported = exporter.DMSExporter(rules, data_model_id=data_model.as_id()).export()

    assert exported.data_model.dump() == data_model.as_apply().dump()


def test_import_json_export_data_model():
    expected_model = CAPACITY_BID_MODEL
    expected_containers = CAPACITY_BID_CONTAINERS

    rules = importer.ArbitraryJSONImporter(CAPACITY_BID_JSON).to_rules()
    exported = exporter.DMSExporter(rules, data_model_id=expected_model.as_id()).export()

    exported.data_model.name = expected_model.name
    exported.data_model.description = expected_model.description

    assert exported.containers.dump() == expected_containers.dump()
    assert exported.data_model.dump() == expected_model.dump()
