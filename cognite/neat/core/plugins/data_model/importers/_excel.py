from pathlib import Path
from typing import Any

from cognite.neat.core._data_model.importers._spreadsheet2data_model import ExcelImporter

from ._base import DataModelImporter

__all__ = ["ExcelDataModelImporter"]


class ExcelDataModelImporter(DataModelImporter):
    def configure(self, source: str, **kwargs: Any) -> ExcelImporter:
        """
        Configures Excel importer.

        Args:
            source (str): Path to the Excel file.
        """

        return ExcelImporter(filepath=Path(source))
