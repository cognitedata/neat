from pathlib import Path

from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._utils.useful_types import DataModelTableType

from ._base import DMSExporter


class DMSTableExporter(DMSExporter[DataModelTableType]):
    """Exports DMS to a table structure.

    The tables are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def export(self, data_model: RequestSchema) -> DataModelTableType:
        raise NotImplementedError()

    def as_excel(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as an Excel file.

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the Excel file to create.
        """
        raise NotImplementedError()

    def as_yaml(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as a YAML file.

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the YAML file to create.
        """
        raise NotImplementedError()
