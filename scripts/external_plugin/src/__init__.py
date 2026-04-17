from pathlib import Path
from typing import ClassVar

from cognite.neat._plugin_adapter import PhysicalDataModelReaderPlugin, PhysicalDataModelFileWriterPlugin
from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.exporters import DMSExcelExporter


class ExternalDataModelReaderPlugin(PhysicalDataModelReaderPlugin):
    """Real ExcelDataModelImporter implementation for testing."""
    method_name: ClassVar[str] = "external_excel"

    def configure(self, io: str) -> DMSTableImporter:
        """
        Configures Excel importer.

        Args:
            io (str): Path to the Excel file.
        """
        return DMSTableImporter.from_excel(excel_file=Path(io))


class ExternalDataModelFileWriterPlugin(PhysicalDataModelFileWriterPlugin):
    """Real ExcelDataModelExporter implementation for testing."""
    method_name: ClassVar[str] = "external_excel"

    def configure(self, **kwargs) -> DMSExcelExporter:
        """
        Configures Excel exporter.

        Args:
            **kwargs (Any): Keyword arguments for plugin configuration.
                            The specific arguments depend on the plugin implementation.
        Returns:
            DMSExcelExporter: An instance of DMSExcelExporter, specialized for given plugin
        """
        return DMSExcelExporter(**kwargs)


__all__ = ["ExternalDataModelReaderPlugin", "ExternalDataModelFileWriterPlugin"]