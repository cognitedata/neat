import pytest

from cognite.neat._plugin._interfaces import PhysicalDataModelReaderPlugin
from cognite.neat._plugin._manager import PluginManager


class TestPlugin(PhysicalDataModelReaderPlugin): ...


@pytest.fixture
def manager() -> PluginManager:
    mng = PluginManager.load_plugins()
    return mng


class TestPluginManager:
    def test_plugin_loaded(self, manager: PluginManager) -> None:
        """Test loading an external plugin."""
        # Assuming external plugins are discovered automatically
        assert len(manager.get(PhysicalDataModelReaderPlugin)) == 1, "No PhysicalDataModelReaderPlugin found"
        assert len(manager.get(TestPlugin)) == 0, "TestPlugin should not be loaded"
