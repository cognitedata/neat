from pathlib import Path

from cognite.neat.core._data_model.importers._spreadsheet2data_model import ExcelImporter

from ._base import DataModelImporterPlugin

__all__ = ["ExcelDataModelImporterPlugin"]


class ExcelDataModelImporterPlugin(DataModelImporterPlugin):
    def configure(self, source: str) -> ExcelImporter:
        """
        Configures Excel importer.

        Args:
            source (str): Path to the Excel file.
        """

        return ExcelImporter(filepath=Path(source))
