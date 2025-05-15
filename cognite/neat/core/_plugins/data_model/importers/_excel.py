from pathlib import Path

from cognite.neat.core._data_model._shared import (
    ImportedDataModel,
)
from cognite.neat.core._data_model.importers._spreadsheet2data_model import ExcelImporter
from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.physical._unverified import (
    UnverifiedPhysicalDataModel,
)

from ._base import DataModelImporterPlugin

__all__ = ["ExcelDataModelImporterPlugin"]


class ExcelDataModelImporterPlugin(DataModelImporterPlugin):
    def import_data_model(
        self, source: str
    ) -> ImportedDataModel[UnverifiedPhysicalDataModel] | ImportedDataModel[UnverifiedConceptualDataModel]:
        """
        Imports data model from an Excel file.

        Args:
            source (str): Path to the Excel file.
            validate (bool): Whether to validate the rules.
        """

        return ExcelImporter(filepath=Path(source)).to_data_model()
