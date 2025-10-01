from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._utils.useful_types import CellValue

from ._base import DMSImporter


class DMSTableImporter(DMSImporter):
    """Imports DMS from a table structure.

    The tables can are expected to be a dictionary where the keys are the table names and the values
    are lists of dictionaries representing the rows in the table.
    """

    def __init__(self, tables: dict[str, list[dict[str, CellValue]]]) -> None:
        self._table = tables

    def to_data_model(self) -> RequestSchema:
        raise NotImplementedError()
