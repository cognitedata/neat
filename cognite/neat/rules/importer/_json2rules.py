import json
from pathlib import Path
from typing import Literal

from ._dict2rules import ArbitraryDictImporter


class ArbitraryJSONImporter(ArbitraryDictImporter):
    """
    Importer for data given in a JSON file or string.

    This importer infers the data model from the JSON string based on the shape of the data.

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
