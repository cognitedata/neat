import contextlib
import io
from importlib.metadata import EntryPoint, EntryPoints
from pathlib import Path
from typing import Any

import pytest

from cognite.neat import NeatSession
from cognite.neat.v0.core._data_model.importers._spreadsheet2data_model import ExcelImporter
from cognite.neat.v0.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)
from cognite.neat.v0.plugins import DataModelImporterPlugin, _manager
from cognite.neat.v0.plugins._issues import (
    PluginDuplicateError,
    PluginLoadingError,
)
from cognite.neat.v0.plugins._manager import PluginManager
from tests.v0.data import SchemaData


class ExcelDataModelImporterPlugin(DataModelImporterPlugin):
    """Real ExcelDataModelImporter implementation for testing."""

    def configure(self, io: Path, **kwargs: Any) -> ExcelImporter:
        """
        Configures Excel importer.

        Args:
            source (str): Path to the Excel file.
        """

        return ExcelImporter(filepath=io)


@pytest.fixture
def neat_plugin_entry_points():
    """Create a mock entry point for testing."""

    return EntryPoints(
        [
            EntryPoint(
                name="excel",
                group="cognite.neat.v0.plugins.data_model.importers",
                value="tests.v0.tests_unit.test_plugins:ExcelDataModelImporterPlugin",
            )
        ]
    )


@pytest.fixture
def none_neat_plugin_entry_points():
    """Create a mock entry point for testing."""

    return EntryPoints(
        [EntryPoint(name="ox-turtle", group="rdf.plugins.parser", value="oxrdflib.parser:OxigraphTurtleParser")]
    )


@pytest.fixture
def duplicated_neat_plugin():
    """Create a mock entry point for testing."""

    return EntryPoints(
        [
            EntryPoint(
                name="excel",
                group="cognite.neat.v0.plugins.data_model.importers",
                value="tests.v0.tests_unit.test_plugins:ExcelDataModelImporterPlugin",
            ),
            EntryPoint(
                name="excel",
                group="cognite.neat.v0.plugins.data_model.importers",
                value="tests.v0.test_plugins:ExcelDataModelImporterPlugin",
            ),
        ]
    )


@pytest.fixture
def non_loadable_neat_plugin():
    """Create a mock entry point for testing."""

    return EntryPoints(
        [
            EntryPoint(
                name="excel",
                group="cognite.neat.v0.plugins.data_model.importers",
                value="tests.v0.test_plugins:ExcelDataModelImporterPlugin",
            )
        ]
    )


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


def test_load_neat_plugin(neat_plugin_entry_points):
    """Test ExternalPlugin initialization."""
    manager = PluginManager.load_plugins(neat_plugin_entry_points)
    assert len(manager._plugins) == 1


def test_dont_load_none_neat_plugin(none_neat_plugin_entry_points):
    """Test ExternalPlugin initialization."""
    manager = PluginManager.load_plugins(none_neat_plugin_entry_points)
    assert len(manager._plugins) == 0


def test_duplicated_plugin_error(duplicated_neat_plugin):
    """Test that registering a plugin with the same name raises an error."""
    with pytest.raises(PluginDuplicateError):
        PluginManager.load_plugins(duplicated_neat_plugin)


def test_load_plugin_error(non_loadable_neat_plugin):
    """Test that registering a plugin with the same name raises an error."""
    with pytest.raises(PluginLoadingError):
        PluginManager.load_plugins(non_loadable_neat_plugin)


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
