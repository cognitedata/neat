import json
from pathlib import Path
from typing import cast

import yaml

from cognite.neat._data_model.exporters._base import DMSExporter, DMSFileExporter
from cognite.neat._data_model.importers._table_importer.data_classes import DMSProperty, TableDMS
from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._utils.useful_types import DataModelTableType

from .workbook import WorkbookCreator, WorkbookOptions
from .writer import DMSTableWriter


class DMSTableExporter(DMSExporter[DataModelTableType]):
    """Exports DMS to a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    class Sheets:
        properties = cast(str, TableDMS.model_fields["properties"].validation_alias)

    def __init__(self, exclude_none: bool = False, skip_properties_in_other_spaces: bool = True) -> None:
        self._exclude_none = exclude_none
        self._skip_properties_in_other_spaces = skip_properties_in_other_spaces

    def export(self, data_model: RequestSchema) -> DataModelTableType:
        model = data_model.data_model
        tables = DMSTableWriter(model.space, model.version, self._skip_properties_in_other_spaces).write_tables(
            data_model
        )
        exclude: set[str] = set()
        if self._exclude_none:
            if not tables.enum:
                exclude.add("enum")
            if not tables.nodes:
                exclude.add("nodes")
            if not tables.containers:
                exclude.add("containers")

        output = tables.model_dump(mode="json", by_alias=True, exclude_none=self._exclude_none, exclude=exclude)
        # When we have exclude_none we only want to exclude none of optional properties, not required.
        # Thus, we do the implementation below
        required_properties = [
            field_.serialization_alias for field_ in DMSProperty.model_fields.values() if field_.is_required()
        ]
        for row in output[self.Sheets.properties]:
            for prop in required_properties:
                if prop not in row:
                    row[prop] = None
        return output


class DMSTableYamlExporter(DMSTableExporter, DMSFileExporter[DataModelTableType]):
    """Exports DMS to YAML."""

    def __init__(self) -> None:
        super().__init__(exclude_none=True)

    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as a flat YAML file, which is identical to the spreadsheet representation

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the YAML file to create.
        """
        table_format = self.export(data_model)
        file_path.write_text(
            yaml.safe_dump(table_format, sort_keys=False), encoding=self.ENCODING, newline=self.NEW_LINE
        )


class DMSTableJSONExporter(DMSTableExporter, DMSFileExporter[DataModelTableType]):
    """Exports DMS to JSON."""

    def __init__(self) -> None:
        super().__init__(exclude_none=True)

    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as a flat JSON file, which is identical to the spreadsheet representation

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the JSON file to create.
        """
        table_format = self.export(data_model)
        file_path.write_text(json.dumps(table_format), encoding=self.ENCODING, newline=self.NEW_LINE)


class DMSExcelExporter(DMSTableExporter, DMSFileExporter[DataModelTableType]):
    """Exports DMS to Excel file."""

    def __init__(self, options: WorkbookOptions | None = None) -> None:
        self._options = options or WorkbookOptions()
        super().__init__(
            exclude_none=False, skip_properties_in_other_spaces=self._options.skip_properties_in_other_spaces
        )

    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        """Exports the data model as a Excel file.

        Args:
            data_model (RequestSchema): The data model to export.
            file_path (Path): The path to the Excel file to create.
            options (WorkbookOptions | None): Options for creating the workbook.
        """
        table_format = self.export(data_model)
        workbook = WorkbookCreator(self._options).create_workbook(table_format)
        try:
            workbook.save(file_path)
        finally:
            workbook.close()


class DMSCsvExporter(DMSTableExporter, DMSFileExporter[DataModelTableType]):
    """Exports DMS to CSV files in a directory."""

    def export_to_file(self, data_model: RequestSchema, directory_path: Path) -> None:
        """Exports the data model as a set of CSV files, one for each table.

        Args:
            data_model (RequestSchema): The data model to export.
            directory_path (Path): The path to the directory to create the CSV files in.
        """
        raise NotImplementedError()
