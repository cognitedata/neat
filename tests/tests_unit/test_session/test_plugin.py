import contextlib
import io

import pytest

from cognite.neat import NeatSession
from cognite.neat.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)
from cognite.neat.plugins import _manager
from tests.data import SchemaData


@pytest.fixture
def mock_external_plugin(neat_plugin_entry_points):
    """Setup and teardown plugin manager for testing."""
    # Store original manager instance
    original_manager = _manager._manager_instance

    # Setup: Load plugins with test entry points
    _manager._manager_instance = _manager.PluginManager.load_plugins(neat_plugin_entry_points)

    yield  # This is where the test runs

    # Teardown: Restore original manager instance
    _manager._manager_instance = original_manager


def test_plugin_error_handling():
    """Test that the plugin API raises the correct error when no plugin is found."""
    neat = NeatSession()

    # Neat Session does not raise an error, but prints it.
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        neat.plugins.data_model.read("csv", "./test.txt")

    printed_statements = output.getvalue()
    assert printed_statements == (
        "[ERROR] PluginError: No plugin of type 'DataModelImporterPlugin' registered \nunder name 'csv'\n"
    )


def test_plugin_read(mock_external_plugin):
    neat = NeatSession()
    neat.plugins.data_model.read("excel", SchemaData.Conceptual.info_arch_car_rules_xlsx)

    assert isinstance(
        neat._state.data_model_store.last_verified_conceptual_data_model,
        ConceptualDataModel,
    )
