from pathlib import Path

import pytest

from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.importers._toolkit_variables import (
    find_toolkit_project_root,
    load_toolkit_variables,
    populate_toolkit_governed_spaces,
    resolve_toolkit_config_paths,
    substitute_toolkit_variables,
)
from cognite.neat._exceptions import FileReadException

TOOLKIT_FIXTURE = Path(__file__).resolve().parents[2] / "data" / "toolkit_substitution"
DATA_MODEL_DIR = TOOLKIT_FIXTURE / "modules" / "test" / "data_modeling" / "my_model"


class TestToolkitVariables:
    def test_find_toolkit_project_root(self) -> None:
        root = find_toolkit_project_root(DATA_MODEL_DIR)
        assert root == TOOLKIT_FIXTURE

    def test_repo_cdf_toml_does_not_hijack_unrelated_paths(self) -> None:
        unrelated = Path(__file__).resolve().parents[2] / "data" / "snapshots" / "local" / "cyclic_reverse_only"
        assert find_toolkit_project_root(unrelated) is None

    def test_resolve_config_prefers_dev_overlay(self) -> None:
        paths = resolve_toolkit_config_paths(TOOLKIT_FIXTURE)
        assert paths == [TOOLKIT_FIXTURE / "default.config.yaml", TOOLKIT_FIXTURE / "config.dev.yaml"]

    def test_module_variables_override_env_and_globals(self) -> None:
        variables = load_toolkit_variables(DATA_MODEL_DIR)
        assert variables["schemaSpace"] == "module_space"
        assert variables["version"] == "1"
        assert variables["viewVersion"] == "1"

    def test_toolkit_version_override(self) -> None:
        variables = load_toolkit_variables(DATA_MODEL_DIR, toolkit_version="9")
        assert variables["version"] == "9"
        assert variables["viewVersion"] == "9"

    def test_substitute_unresolved_raises(self) -> None:
        with pytest.raises(FileReadException, match="Unresolved toolkit variable"):
            substitute_toolkit_variables("space: {{ missingVar }}", {}, source="test.yaml")

    def test_import_toolkit_directory_resolves_placeholders(self) -> None:
        importer = DMSAPIImporter.from_yaml(DATA_MODEL_DIR)
        schema = importer.to_data_model()

        assert schema.data_model.space == "module_space"
        assert schema.data_model.version == "1"
        assert len(schema.views) == 1
        assert schema.views[0].space == "module_space"
        assert schema.views[0].version == "1"
        assert len(schema.containers) == 1
        assert schema.containers[0].space == "module_space"

    def test_import_with_string_data_model_file_path(self) -> None:
        importer = DMSAPIImporter.from_yaml(
            DATA_MODEL_DIR,
            data_model_file="MyModel.datamodel.yaml",
        )
        schema = importer.to_data_model()
        assert schema.data_model.external_id == "MyModel"

    def test_import_with_explicit_env_overlay(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        model_dir = project / "modules" / "mod" / "data_modeling" / "dm"
        model_dir.mkdir(parents=True)

        (project / "default.config.yaml").write_text(
            "variables:\n  schemaSpace: base_space\n  viewVersion: v1\n",
            encoding="utf-8",
        )
        (project / "config.prod.yaml").write_text(
            "variables:\n  schemaSpace: prod_space\n",
            encoding="utf-8",
        )
        (model_dir / "Model.datamodel.yaml").write_text(
            "space: {{ schemaSpace }}\nexternalId: Model\nversion: {{ viewVersion }}\nviews: []\n",
            encoding="utf-8",
        )

        importer = DMSAPIImporter.from_yaml(model_dir, toolkit_env="prod")
        schema = importer.to_data_model()
        assert schema.data_model.space == "prod_space"
        assert schema.data_model.version == "v1"

    def test_org_directory_config_layout(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        org = project / "beyond-the-plant"
        model_dir = org / "modules" / "btp" / "data_modeling" / "dm"
        model_dir.mkdir(parents=True)

        (project / "cdf.toml").write_text(
            '[cdf]\ndefault_organization_dir = "beyond-the-plant"\ndefault_env = "dev"\n',
            encoding="utf-8",
        )
        (org / "config.dev.yaml").write_text(
            "variables:\n  version: v1.5.0\n  viewVersion: v1.5.0\n  isaSchemaSpace: sp_test\n",
            encoding="utf-8",
        )
        (model_dir / "Model.datamodel.yaml").write_text(
            "space: {{ isaSchemaSpace }}\nexternalId: Model\nversion: {{ version }}\nviews: []\n",
            encoding="utf-8",
        )

        paths = resolve_toolkit_config_paths(project)
        assert paths == [org / "config.dev.yaml"]

        variables = load_toolkit_variables(model_dir)
        assert variables["version"] == "v1.5.0"
        assert variables["isaSchemaSpace"] == "sp_test"

        importer = DMSAPIImporter.from_yaml(model_dir)
        schema = importer.to_data_model()
        assert schema.data_model.space == "sp_test"
        assert schema.data_model.version == "v1.5.0"


class TestToolkitGovernedSpaces:
    def test_populates_governed_spaces_from_local_spaces(self, tmp_path: Path) -> None:
        model_dir = tmp_path / "modules" / "mod" / "data_modeling" / "dm"
        model_dir.mkdir(parents=True)

        (model_dir / "Model.datamodel.yaml").write_text(
            "space: dm_space\nexternalId: Model\nversion: v1\nviews: []\n",
            encoding="utf-8",
        )
        (model_dir / "records.Space.yaml").write_text("space: records_space\n", encoding="utf-8")
        (model_dir / "Record.container.yaml").write_text(
            "space: records_space\nexternalId: Record\nproperties:\n  id:\n    type:\n      type: text\n",
            encoding="utf-8",
        )
        (model_dir / "Record.view.yaml").write_text(
            "space: records_space\nexternalId: Record\nversion: v1\nproperties:\n  id:\n"
            "    container:\n      space: records_space\n      externalId: Record\n"
            "      type: container\n    containerPropertyIdentifier: id\n",
            encoding="utf-8",
        )

        schema = DMSAPIImporter.from_yaml(model_dir).to_data_model()
        assert schema.governed_space_set() == {"dm_space", "records_space"}

    def test_does_not_override_explicit_governed_spaces(self, tmp_path: Path) -> None:
        from cognite.neat._data_model.models.dms import DataModelRequest, RequestSchema, SpaceRequest
        from cognite.neat._data_model.models.dms._schema import SchemaExtra

        schema = RequestSchema(
            dataModel=DataModelRequest(space="dm_space", externalId="Model", version="v1", views=[]),
            extra=SchemaExtra(governedSpaces=[SpaceRequest(space="explicit_space")]),
        )
        updated = populate_toolkit_governed_spaces(schema)
        assert {space.space for space in updated.extra.governed_spaces} == {"explicit_space"}
