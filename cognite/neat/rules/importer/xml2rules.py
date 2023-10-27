from pathlib import Path

import pandas as pd

from cognite.neat.rules.importer._base import BaseImporter


class XMLImporter(BaseImporter):
    """
    Importer for XML files.

    Args:
        xml_directory: Path to directory containing XML files.
    """

    def __init__(self, xml_directory: Path):
        self.xml_directory = xml_directory

    def to_tables(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError
