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
        {
            "MyModel.datamodel.yaml": """space: my_space
externalId: MyModel
version: '1_0_0'
views:
- space: my_space
  externalId: MyView
  version: '1_0_0'
  type: view
""",
            "views/MyView.view.yaml": """space: my_space
externalId: MyView
version: '1_0_0'
properties:
  name:
    container:
      space: my_space
      externalId: MyContainer
      type: container
    containerPropertyIdentifier: name
""",
            "containers/MyContainer.container.yaml": """space: my_space
externalId: MyContainer
properties:
  name:
    type:
      type: text
""",
        },
        id="Handle integer in version field",
    )


class TestImportYAMLAPIFormat:
    @pytest.mark.parametrize(
        "source, expected",
        list(valid_dms_yaml_formats_roundtrip()),
    )
    def test_roundtrip(self, source: str, expected: dict[str, str]) -> None:
        yaml_file = MagicMock(spec=Path)
        yaml_file.suffix = ".yaml"
        yaml_file.read_text.return_value = source

        data_model = DMSAPIImporter.from_yaml(yaml_file).to_data_model()

        written_files: dict[str, str] = {}

        def make_mock_path(name: str = "root") -> MagicMock:
            mock = MagicMock(spec=Path)
            mock.suffix = ""
            mock.write_text = MagicMock(side_effect=lambda content, **_: written_files.update({name: content}))
            mock.__truediv__ = lambda self, other: make_mock_path(str(other))
            return mock

        yaml_dir = make_mock_path()
        DMSAPIYAMLExporter().export_to_file(data_model, yaml_dir)
        assert expected == written_files
