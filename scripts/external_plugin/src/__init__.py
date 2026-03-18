from pathlib import Path

from cognite.neat._plugin_adapter import PhysicalDataModelReaderPlugin
from cognite.neat._data_model.importers import DMSTableImporter


class ExternalDataModelReaderPlugin(PhysicalDataModelReaderPlugin):
    """Real ExcelDataModelImporter implementation for testing."""

    def configure(self, io: str) -> DMSTableImporter:
        """
        Configures Excel importer.

        Args:
            io (str): Path to the Excel file.
        """
        return DMSTableImporter.from_excel(excel_file=Path(io))


__all__ = ["ExcelDataModelReaderPlugin"]