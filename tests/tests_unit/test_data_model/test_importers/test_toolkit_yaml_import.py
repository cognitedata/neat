from pathlib import Path
from typing import Any

import pytest

from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.importers._toolkit_variables import (
    find_toolkit_project_root,
    substitute_toolkit_variables,
)
from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._exceptions import FileReadException

TOOLKIT_FIXTURE = Path(__file__).resolve().parents[3] / "data" / "toolkit_substitution"
DATA_MODEL_DIR = TOOLKIT_FIXTURE / "modules" / "test" / "data_modeling" / "my_model"
CYCLIC_REVERSE_ONLY = Path(__file__).resolve().parents[3] / "data" / "snapshots" / "local" / "cyclic_reverse_only"


def _import_schema(model_dir: Path, **kwargs: Any) -> RequestSchema:
    return DMSAPIImporter.from_yaml(model_dir, **kwargs).to_data_model()


class TestToolkitYamlImport:
    def test_import_resolves_variables(self) -> None:
        assert find_toolkit_project_root(DATA_MODEL_DIR) == TOOLKIT_FIXTURE

        schema = _import_schema(DATA_MODEL_DIR)

        assert schema.data_model.space == "module_space"
        assert schema.data_model.external_id == "MyModel"
        assert schema.data_model.version == "1"

    @pytest.mark.parametrize(
        ("kwargs", "assertions"),
        [
            pytest.param(
                {"data_model_file": "MyModel.datamodel.yaml"},
                lambda schema: schema.data_model.external_id == "MyModel",
                id="explicit-data-model-file",
            ),
            pytest.param(
                {"toolkit_version": "9"},
                lambda schema: schema.data_model.version == "9" and all(view.version == "9" for view in schema.views),
                id="toolkit-version-override",
            ),
        ],
    )
    def test_import_options(self, kwargs: dict[str, Any], assertions: Any) -> None:
        schema = _import_schema(DATA_MODEL_DIR, **kwargs)
        assert assertions(schema)

    @pytest.mark.parametrize(
        "layout",
        [
            pytest.param("prod-overlay", id="prod-overlay"),
            pytest.param("cdf-toml-org", id="cdf-toml-org"),
        ],
    )
    def test_import_alternate_toolkit_config_layouts(self, tmp_path: Path, layout: str) -> None:
        project = tmp_path / "project"

        if layout == "prod-overlay":
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
            schema = _import_schema(model_dir, toolkit_env="prod")
            assert schema.data_model.space == "prod_space"
            assert schema.data_model.version == "v1"
            return

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
        schema = _import_schema(model_dir)
        assert schema.data_model.space == "sp_test"
        assert schema.data_model.version == "v1.5.0"

    def test_load_globals_from_modules_level_without_default_config(self, tmp_path: Path) -> None:
        """Match Toolkit projects that only ship config.<env>.yaml with globals under variables.modules."""
        project = tmp_path / "project"
        model_dir = project / "modules" / "pidm" / "data_models"
        model_dir.mkdir(parents=True)
        (project / "cdf.toml").write_text(
            '[cdf]\ndefault_config_yaml = "config.dev.yaml"\n',
            encoding="utf-8",
        )
        (project / "config.dev.yaml").write_text(
            "variables:\n  modules:\n    dm_sol_pidm_version: v0.1.15\n",
            encoding="utf-8",
        )
        (model_dir / "Model.datamodel.yaml").write_text(
            "space: sp_pidm\nexternalId: Model\nversion: {{ dm_sol_pidm_version }}\nviews: []\n",
            encoding="utf-8",
        )

        schema = _import_schema(model_dir)
        assert schema.data_model.version == "v0.1.15"

    def test_sandbox_overlay_wins_over_dev_and_module_default(self, tmp_path: Path) -> None:
        """cdf.toml default_config_yaml=sandbox must win even when config.dev.yaml exists.

        Module-local default.config.yaml must not become the project root.
        """
        project = tmp_path / "digital-twin-dev"
        module = project / "modules" / "emergency360"
        model_dir = module / "data_modeling" / "dm"
        model_dir.mkdir(parents=True)
        (project / "cdf.toml").write_text(
            '[cdf]\ndefault_config_yaml = "config.sandbox.yaml"\n',
            encoding="utf-8",
        )
        (project / "config.dev.yaml").write_text(
            "variables:\n  modules:\n    viewVersion: v-dev\n    YGGDRASIL_INSTANCE_SPACE: ygg-dev\n",
            encoding="utf-8",
        )
        (project / "config.sandbox.yaml").write_text(
            "variables:\n  modules:\n    viewVersion: v-sbx\n    YGGDRASIL_INSTANCE_SPACE: ygg\n",
            encoding="utf-8",
        )
        (module / "default.config.yaml").write_text(
            "E360_PREFIX: E360\nYGGDRASIL_INSTANCE_SPACE: ygg-module\n",
            encoding="utf-8",
        )
        (model_dir / "Model.datamodel.yaml").write_text(
            "space: {{ YGGDRASIL_INSTANCE_SPACE }}\nexternalId: {{ E360_PREFIX }}\n"
            "version: {{ viewVersion }}\nviews: []\n",
            encoding="utf-8",
        )

        assert find_toolkit_project_root(model_dir) == project
        schema = _import_schema(model_dir)
        assert schema.data_model.space == "ygg"
        assert schema.data_model.external_id == "E360"
        assert schema.data_model.version == "v-sbx"

        schema_dev = _import_schema(model_dir, toolkit_env="dev")
        assert schema_dev.data_model.version == "v-dev"
        assert schema_dev.data_model.space == "ygg-dev"

    def test_project_root_and_parent_folder_resolve_sandbox(self, tmp_path: Path) -> None:
        """read.yaml(io=project) and io=parent-of-project must find cdf.toml + sandbox overlay."""
        parent = tmp_path / "ABP-digital-twin"
        project = parent / "digital-twin-dev"
        model_dir = project / "modules" / "emergency360" / "data_modeling" / "dm"
        model_dir.mkdir(parents=True)
        (project / "cdf.toml").write_text(
            '[cdf]\ndefault_config_yaml = "config.sandbox.yaml"\n',
            encoding="utf-8",
        )
        (project / "config.sandbox.yaml").write_text(
            "variables:\n  modules:\n    ep_id_prefix: '[abp-sbx]'\n    viewVersion: v1\n"
            "    schemaSpace: sandbox_space\n",
            encoding="utf-8",
        )
        (project / "build_info.dev.yaml").write_text(
            "modules:\n  version: 0.8.103\n  # {{ ep_id_prefix }} must not be substituted in this file\n",
            encoding="utf-8",
        )
        (model_dir / "Model.datamodel.yaml").write_text(
            "space: {{ schemaSpace }}\nexternalId: Model\nversion: {{ viewVersion }}\nviews: []\n",
            encoding="utf-8",
        )

        assert find_toolkit_project_root(project) == project
        assert find_toolkit_project_root(parent) == project

        schema = _import_schema(parent, data_model_file="Model.datamodel.yaml")
        assert schema.data_model.space == "sandbox_space"
        assert schema.data_model.version == "v1"

    def test_repo_cdf_toml_does_not_hijack_unrelated_paths(self) -> None:
        assert find_toolkit_project_root(CYCLIC_REVERSE_ONLY) is None

    def test_substitute_unresolved_raises(self) -> None:
        with pytest.raises(FileReadException, match="Unresolved toolkit variable"):
            substitute_toolkit_variables("space: {{ missingVar }}", {}, source="test.yaml")
