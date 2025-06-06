from importlib.metadata import EntryPoint, EntryPoints
from pathlib import Path
from typing import Any

import pytest

from cognite.neat.core._data_model.importers._spreadsheet2data_model import ExcelImporter
from cognite.neat.plugins._issues import (
    PluginDuplicateError,
    PluginLoadingError,
)
from cognite.neat.plugins._manager import PluginManager
from cognite.neat.plugins.data_model.importers import DataModelImporterPlugin


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
                group="cognite.neat.plugins.data_model.importers",
                value="tests.tests_unit.test_plugins:ExcelDataModelImporterPlugin",
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
                group="cognite.neat.plugins.data_model.importers",
                value="tests.tests_unit.test_plugins:ExcelDataModelImporterPlugin",
            ),
            EntryPoint(
                name="excel",
                group="cognite.neat.plugins.data_model.importers",
                value="tests.test_plugins:ExcelDataModelImporterPlugin",
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
                group="cognite.neat.plugins.data_model.importers",
                value="tests.test_plugins:ExcelDataModelImporterPlugin",
            )
        ]
    )


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
