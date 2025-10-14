from pathlib import Path

from cognite.neat._data_model.exporters._base import DMSExporter
from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._utils.useful_types import DataModelTableType

from .writer import DMSTableWriter


class DMSTableExporter(DMSExporter[DataModelTableType]):
    """Exports DMS to a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, exclude_none: bool = False) -> None:
        self._exclude_none = exclude_none

    def export(self, data_model: RequestSchema) -> DataModelTableType:
        model = data_model.data_model
        tables = DMSTableWriter(model.space, model.external_id).write_tables(data_model)
        return tables.model_dump(mode="json", by_alias=True, exclude_none=self._exclude_none)

    def as_excel(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as an Excel file.

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the Excel file to create.
        """
        raise NotImplementedError()

    def as_yaml(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as a flat YAML file, which is identical to the spreadsheet representation

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the YAML file to create.
        """
        raise NotImplementedError()

    def as_csvs(self, data_model: RequestSchema, directory_path: Path) -> None:
        """Exports the data model as a set of CSV files, one for each table.

        Args:
            data_model (RequestSchema): The data model to export.
            directory_path (Path): The path to the directory to create the CSV files in.
        """
        raise NotImplementedError()
