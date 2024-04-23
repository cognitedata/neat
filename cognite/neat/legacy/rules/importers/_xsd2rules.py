from pathlib import Path

import pandas as pd

from ._base import BaseImporter


class XSDImporter(BaseImporter):
    """
    Importer for XSD (XML Schema) files.

    Args:
        xml_directory: Path to directory containing XSD files.
    """

    def __init__(self, xsd_directory: Path):
        self.xsd_directory = xsd_directory

    def to_tables(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError
