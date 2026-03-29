from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cognite.neat._data_model.exporters import DMSAPIYAMLExporter
from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.models.dms import RequestSchema


def valid_dms_yaml_formats_roundtrip() -> Iterable[tuple]:
    yield pytest.param(
        {
            "dataModel": """  space: my_space
  externalId: MyModel
  version: 1_0_0
  views:
  - space: my_space
    externalId: MyView
    version: 1_0_0""",
            "views": """- space: my_space
  externalId: MyView
  version: 1_0_0
  properties:
    name:
      container:
        space: my_space
        externalId: MyContainer
      containerPropertyIdentifier: name
""",
            "containers": """- space: my_space
  externalId: MyContainer
  properties:
    name:
      type:
        type: text
""",
        },
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
    @pytest.mark.parametrize("source, expected", list(valid_dms_yaml_formats_roundtrip()))
    def test_roundtrip_single_input_file(self, source: dict[str, str], expected: dict[str, str]) -> None:
        source_content: list[str] = []
        for key, value in source.items():
            source_content.extend([f"{key}:", value])
        yaml_file = MagicMock(spec=Path)
        yaml_file.suffix = ".yaml"
        yaml_file.read_text.return_value = "\n".join(source_content)

        data_model = DMSAPIImporter.from_yaml(yaml_file).to_data_model()

        self.assert_written_output(data_model, expected)

    @pytest.mark.parametrize("source, expected", list(valid_dms_yaml_formats_roundtrip()))
    def test_roundtrip_directory_input(self, source: dict[str, str], expected: dict[str, str]) -> None:
        yaml_dir = MagicMock(spec=Path)
        yaml_dir.is_dir.return_value = True
        yaml_dir.rglob.return_value = [
            # File kind is singular.
            self._make_mock_file(kind.removesuffix("s"), content)
            for kind, content in source.items()
        ]

        data_model = DMSAPIImporter.from_yaml(yaml_dir).to_data_model()

        self.assert_written_output(data_model, expected)

    def _make_mock_file(self, kind: str, content: str) -> MagicMock:
        yaml_file = MagicMock(spec=Path)
        yaml_file.suffix = ".yaml"
        yaml_file.read_text.return_value = content
        yaml_file.stem = f"my.{kind}"
        yaml_file.name = f"{yaml_file.stem}{yaml_file.suffix}"
        return yaml_file

    def assert_written_output(self, data_model: RequestSchema, expected: dict[str, str]) -> None:
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
