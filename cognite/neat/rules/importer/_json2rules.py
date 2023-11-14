import json
from pathlib import Path
from typing import Literal

from ._dict2rules import DictImporter


class JSONImporter(DictImporter):
    """
    Importer for JSON files to raw dataframes.

    Args:
        json_path_or_str: Path to file with JSON or a JSON string.
        relationship_direction: Direction of relationships, either "parent-to-child" or "child-to-parent". JSON
            files are nested with children nested inside parents. This option determines whether the resulting rules
            will have an edge from parents to children or from children to parents.

    """

    def __init__(
        self,
        json_path_or_str: Path,
        relationship_direction: Literal["parent-to-child", "child-to-parent"] = "parent-to-child",
    ):
        if isinstance(json_path_or_str, str):
            data = json.loads(json_path_or_str)
            super().__init__(data, relationship_direction)
        elif isinstance(json_path_or_str, Path):
            if not json_path_or_str.exists():
                raise ValueError(f"File {json_path_or_str} does not exist")
            if json_path_or_str.suffix != ".json":
                raise ValueError(f"File {json_path_or_str} is not a JSON file")
            self.json_path = json_path_or_str
            data = json.loads(json_path_or_str.read_text())
            super().__init__(data, relationship_direction)
        else:
            raise TypeError(f"Expected Path or str, got {type(json_path_or_str)}")
