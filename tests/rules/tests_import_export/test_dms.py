import pytest
from cognite.client import data_modeling as dm

from cognite.neat.rules import exporter, importer
from tests.data import OSDUWELLS_MODEL, SCENARIO_INSTANCE_MODEL


@pytest.mark.parametrize(
    "data_model", [pytest.param(m, id=m.external_id) for m in [OSDUWELLS_MODEL, SCENARIO_INSTANCE_MODEL]]
)
def test_import_export_data_model(data_model: dm.DataModel[dm.View]):
    rules = importer.DMSImporter(data_model).to_rules()

    exported = exporter.DMSExporter(rules, data_model_id=data_model.as_id()).export()

    assert exported.data_model.dump() == data_model.as_apply().dump()
