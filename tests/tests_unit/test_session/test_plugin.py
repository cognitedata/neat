import io
from contextlib import redirect_stdout

from cognite.neat import NeatSession
from tests.data import GraphData, SchemaData


def test_plugin_does_not_exist() -> None:
    neat = NeatSession()

    f = io.StringIO()
    with redirect_stdout(f):
        neat._plugin.data_model.read("imf", GraphData.imf_temp_transmitter_complete_ttl)
    output = f.getvalue()

    assert output == "[ERROR] PluginError: No plugin of kind 'DataModelImporter' registered for \nformat/action 'imf'\n"


def test_excel_importer_plugin() -> None:
    neat = NeatSession()

    neat._plugin.data_model.read("excel", SchemaData.Conceptual.info_arch_car_rules_xlsx)

    assert neat._state.data_model_store.last_verified_data_model.metadata.external_id == "carDataModel"
