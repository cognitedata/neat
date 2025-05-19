import pytest

from cognite.neat.core import _plugin as plugin
from cognite.neat.core.plugins.data_model.importers._base import DataModelImporter


def test_plugin_catalog():
    assert len(plugin._plugins) == 1
    assert all(isinstance(value, plugin.InternalPlugin) for value in plugin._plugins.values())


def test_raise_error():
    with pytest.raises(plugin.PluginError):
        plugin.get("imf", DataModelImporter)
