from pathlib import Path

import yaml

from .dict2tables import DictImporter


class YAMLImporter(DictImporter):
    """
    Importer for yaml file.

    Args:
        yaml_path: Path to file with YAML.

    """

    def __init__(self, yaml_path: Path):
        if not yaml_path.exists():
            raise ValueError(f"File {yaml_path} does not exist")
        if yaml_path.suffix not in {".yml", "yaml"}:
            raise ValueError(f"File {yaml_path} is not a YAML file")
        self.json_path = yaml_path
        data = yaml.safe_load(yaml_path.read_text())
        super().__init__(data=data, spreadsheet_path=yaml_path.parent / "transformation_rules.xlsx")
