import json
from pathlib import Path

from ._dict2rules import DictImporter


class JSONImporter(DictImporter):
    """
    Importer for JSON files to raw dataframes.

    Args:
        json_path_or_str: Path to file with JSON or a JSON string.

    """

    def __init__(self, json_path_or_str: Path):
        if isinstance(json_path_or_str, str):
            data = json.loads(json_path_or_str)
            super().__init__(data=data)
        elif isinstance(json_path_or_str, Path):
            if not json_path_or_str.exists():
                raise ValueError(f"File {json_path_or_str} does not exist")
            if json_path_or_str.suffix != ".json":
                raise ValueError(f"File {json_path_or_str} is not a JSON file")
            self.json_path = json_path_or_str
            data = json.loads(json_path_or_str.read_text())
            super().__init__(data=data)
        else:
            raise TypeError(f"Expected Path or str, got {type(json_path_or_str)}")
