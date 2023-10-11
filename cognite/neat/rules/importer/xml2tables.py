from pathlib import Path

from cognite.neat.rules.parser import RawTables

from ._base import BaseImporter


class XMLImporter(BaseImporter):
    """
    Importer for XML files.

    Args:
        xml_directory: Path to directory containing XML files.
    """

    def __init__(self, xml_directory: Path):
        self.xml_directory = xml_directory
        super().__init__(spreadsheet_path=xml_directory / "transformation_rules.xlsx")

    def to_tables(self) -> RawTables:
        raise NotImplementedError
        # raise NotImplementedError
