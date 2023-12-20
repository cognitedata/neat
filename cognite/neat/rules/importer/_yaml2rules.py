from pathlib import Path
from typing import Literal

import yaml

from cognite.neat.rules.importer._dict2rules import ArbitraryDictImporter


class ArbitraryYAMLImporter(ArbitraryDictImporter):
    """
    Importer for data given in a YAML file or string.

    This importer infers the data model from the YAML string based on the shape of the data.

    Args:
        yaml_path_or_str: Path to file with YAML.
        relationship_direction: Direction of relationships, either "parent-to-child" or "child-to-parent". JSON
            files are nested with children nested inside parents. This option determines whether the resulting rules
            will have an edge from parents to children or from children to parents.
    """

    def __init__(
        self,
        yaml_path_or_str: Path,
        relationship_direction: Literal["parent-to-child", "child-to-parent"] = "parent-to-child",
    ):
        if isinstance(yaml_path_or_str, str):
            data = yaml.safe_load(yaml_path_or_str)
            super().__init__(data, relationship_direction)
        elif isinstance(yaml_path_or_str, Path):
            if not yaml_path_or_str.exists():
                raise ValueError(f"File {yaml_path_or_str} does not exist")
            if yaml_path_or_str.suffix != ".json":
                raise ValueError(f"File {yaml_path_or_str} is not a JSON file")
            self.json_path = yaml_path_or_str
            data = yaml.safe_load(yaml_path_or_str.read_text())
            super().__init__(data, relationship_direction)
        else:
            raise TypeError(f"Expected Path or str, got {type(yaml_path_or_str)}")
