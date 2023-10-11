import json
from pathlib import Path

from .dict2tables import DictImporter


class JSONImporter(DictImporter):
    """
    Importer for JSON files.

    Args:
        json_path: Path to file with JSON.

    """

    def __init__(self, json_path: Path):
        if not json_path.exists():
            raise ValueError(f"File {json_path} does not exist")
        if json_path.suffix != ".json":
            raise ValueError(f"File {json_path} is not a JSON file")
        self.json_path = json_path
        data = json.loads(json_path.read_text())
        super().__init__(data=data, spreadsheet_path=json_path.parent / "transformation_rules.xlsx")
