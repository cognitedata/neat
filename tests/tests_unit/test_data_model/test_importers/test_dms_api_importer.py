from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cognite.neat._data_model.exporters import DMSAPIYAMLExporter
from cognite.neat._data_model.importers import DMSAPIImporter


def valid_dms_yaml_formats_roundtrip() -> Iterable[tuple]:
    yield pytest.param(
        """dataModel:
  space: my_space
  externalId: MyModel
  version: 1_0_0
  views:
  - space: my_space
    externalId: MyView
    version: 1_0_0
views:
- space: my_space
  externalId: MyView
  version: 1_0_0
  properties:
    name:
      container:
        space: my_space
        externalId: MyContainer
      containerPropertyIdentifier: name
containers:
- space: my_space
  externalId: MyContainer
  properties:
    name:
      type:
        type: text
""",
        """dataModel:
  space: my_space
  externalId: MyModel
  version: '1_0_0'
  views:
  - space: my_space
    externalId: MyView
    version: '1_0_0'
views:
- space: my_space
  externalId: MyView
  version: '1_0_0'
  properties:
    name:
      container:
        space: my_space
        externalId: MyContainer
      containerPropertyIdentifier: name
containers:
- space: my_space
  externalId: MyContainer
  properties:
    name:
      type:
        type: text
""",
        id="Handle integer in version field",
    )


class TestImportYAMLAPIFormat:
    @pytest.mark.parametrize(
        "source, expected",
        list(valid_dms_yaml_formats_roundtrip()),
    )
    def test_roundtrip(self, source: str, expected: str) -> None:
        yaml_file = MagicMock(spec=Path)
        yaml_file.suffix = ".yaml"
        yaml_file.read_text.return_value = source

        data_model = DMSAPIImporter.from_yaml(yaml_file).to_data_model()

        yaml_dir = MagicMock(spec=Path)

        DMSAPIYAMLExporter().export_to_file(data_model, yaml_dir)
