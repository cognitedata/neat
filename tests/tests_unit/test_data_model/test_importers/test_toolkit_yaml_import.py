from pathlib import Path
from typing import Any

import pytest

from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.importers._toolkit_variables import (
    find_toolkit_project_root,
    populate_toolkit_governed_spaces,
    substitute_toolkit_variables,
)
from cognite.neat._data_model.models.dms import DataModelRequest, RequestSchema, SpaceRequest
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._schema import SchemaExtra
from cognite.neat._data_model.rules.dms._ai_readiness import EnumerationMissingName
from cognite.neat._data_model.rules.dms._connections import ReverseConnectionContainerMissing
from cognite.neat._data_model.rules.dms._orchestrator import DmsDataModelRulesOrchestrator
from cognite.neat._exceptions import FileReadException

TOOLKIT_FIXTURE = Path(__file__).resolve().parents[3] / "data" / "toolkit_substitution"
DATA_MODEL_DIR = TOOLKIT_FIXTURE / "modules" / "test" / "data_modeling" / "my_model"
CYCLIC_REVERSE_ONLY = Path(__file__).resolve().parents[3] / "data" / "snapshots" / "local" / "cyclic_reverse_only"


def _import_schema(model_dir: Path, **kwargs: Any) -> RequestSchema:
    return DMSAPIImporter.from_yaml(model_dir, **kwargs).to_data_model()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _empty_orchestrator() -> DmsDataModelRulesOrchestrator:
    return DmsDataModelRulesOrchestrator(
        cdf_snapshot=SchemaSnapshot(data_model={}, views={}, containers={}, spaces={}, node_types={}),
        limits=SchemaLimits(),
        modus_operandi="additive",
    )


def _ent_sol_module(tmp_path: Path) -> tuple[Path, Path, Path]:
    modeling = tmp_path / "project" / "modules" / "emergency360" / "data_modeling"
    ent, sol = modeling / "dm_ent", modeling / "dm_sol"
    ent.mkdir(parents=True)
    sol.mkdir(parents=True)
    _write(tmp_path / "project" / "default.config.yaml", "variables:\n  viewVersion: v1\n")
    return modeling, ent, sol


class TestToolkitYamlImport:
    def test_import_resolves_variables_and_derives_governed_spaces(self) -> None:
        assert find_toolkit_project_root(DATA_MODEL_DIR) == TOOLKIT_FIXTURE

        schema = _import_schema(DATA_MODEL_DIR)

        assert schema.data_model.space == "module_space"
        assert schema.data_model.external_id == "MyModel"
        assert schema.data_model.version == "1"
        assert schema.governed_space_set() == {"module_space", "records_space"}

        view_spaces = {view.space for view in schema.views}
        container_spaces = {container.space for container in schema.containers}
        assert view_spaces == {"module_space", "records_space"}
        assert container_spaces == {"module_space", "records_space"}

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

    def test_modules_tree_resolves_nested_variables_per_file(self, tmp_path: Path) -> None:
        """Reading modules/ must use each file's module path for nested Toolkit variables.

        Selecting the solution DataModel still imports a mapped container from another
        module, and must not fail on a sibling DataModel whose version is only defined
        under that sibling module.
        """
        project = tmp_path / "project"
        e360 = project / "modules" / "emergency360" / "data_modeling" / "dm_sol"
        lci = project / "modules" / "lci" / "data_modeling" / "dm_ent"
        valve = project / "modules" / "valve_track" / "data_modeling" / "dm_ent"
        e360.mkdir(parents=True)
        lci.mkdir(parents=True)
        valve.mkdir(parents=True)
        (project / "cdf.toml").write_text(
            '[cdf]\ndefault_config_yaml = "config.sandbox.yaml"\n',
            encoding="utf-8",
        )
        (project / "config.sandbox.yaml").write_text(
            "variables:\n  modules:\n    sp_id_prefix: sp\n    LCI_PREFIX: LCI\n"
            "    emergency360:\n      E360_SOL_DM_VERSION: 1.0.0\n"
            "    valve_track:\n      VALVE_MANAGEMENT_ENT_DM_VERSION: 1.18.0\n",
            encoding="utf-8",
        )
        _write(
            e360 / "Sol.DataModel.yaml",
            "space: {{ sp_id_prefix }}_sol\nexternalId: dm_sol\nversion: {{ E360_SOL_DM_VERSION }}\n"
            "views:\n  - space: {{ sp_id_prefix }}_sol\n    externalId: Tag\n"
            "    version: {{ E360_SOL_DM_VERSION }}\n",
        )
        _write(
            e360 / "Tag.View.yaml",
            "space: {{ sp_id_prefix }}_sol\nexternalId: Tag\nversion: {{ E360_SOL_DM_VERSION }}\n"
            "properties:\n  tagName:\n    container:\n      space: {{ sp_id_prefix }}_ent\n"
            "      externalId: {{ LCI_PREFIX }}Tag\n      type: container\n"
            "    containerPropertyIdentifier: name\n",
        )
        _write(
            lci / "Tag.Container.yaml",
            "space: {{ sp_id_prefix }}_ent\nexternalId: {{ LCI_PREFIX }}Tag\n"
            "properties:\n  name:\n    type:\n      type: text\n",
        )
        _write(
            valve / "Valve.DataModel.yaml",
            "space: {{ sp_id_prefix }}_ent\nexternalId: dm_valve\n"
            "version: {{ VALVE_MANAGEMENT_ENT_DM_VERSION }}\nviews: []\n",
        )

        schema = _import_schema(project / "modules", data_model_file="Sol.DataModel.yaml")
        assert schema.data_model.version == "1.0.0"
        assert {container.external_id for container in schema.containers} == {"LCITag"}

    def test_yamale_schema_files_are_not_treated_as_dms_resources(self, tmp_path: Path) -> None:
        assert DMSAPIImporter._is_toolkit_schema_yaml(tmp_path / "data_model_container.yaml") is False
        assert DMSAPIImporter._is_toolkit_schema_yaml(tmp_path / "Tag.Container.yaml") is True

    def test_selected_data_model_does_not_import_sibling_model_spaces(self, tmp_path: Path) -> None:
        """Enterprise + solution YAML in one module: selecting the enterprise DataModel must not
        pull solution views/spaces into the schema (those showed up in Excel governedSpaces)."""
        modeling, ent, sol = _ent_sol_module(tmp_path)
        _write(
            ent / "Ent.datamodel.yaml",
            "space: sp_ent\nexternalId: dm_ent\nversion: v1\n"
            "views:\n  - space: sp_ent\n    externalId: EntView\n    version: v1\n",
        )
        _write(ent / "EntView.view.yaml", "space: sp_ent\nexternalId: EntView\nversion: v1\nproperties: {}\n")
        _write(
            sol / "Sol.datamodel.yaml",
            "space: sp_sol\nexternalId: dm_sol\nversion: v1\n"
            "views:\n  - space: sp_sol\n    externalId: SolView\n    version: v1\n",
        )
        _write(sol / "SolView.view.yaml", "space: sp_sol\nexternalId: SolView\nversion: v1\nproperties: {}\n")
        _write(sol / "sp_sol.Space.yaml", "space: sp_sol\nname: solution\n")

        schema = _import_schema(modeling, data_model_file="Ent.datamodel.yaml")
        assert schema.data_model.space == "sp_ent"
        assert {view.space for view in schema.views} == {"sp_ent"}
        assert {view.external_id for view in schema.views} == {"EntView"}
        assert all(space.space != "sp_sol" for space in schema.spaces)
        assert "sp_sol" not in schema.governed_space_set()

    def test_selected_solution_model_imports_referenced_enterprise_containers(self, tmp_path: Path) -> None:
        """Solution views map to enterprise containers in a sibling folder. Those containers
        (and containers they require) must be imported so reverse/direct relations validate."""
        modeling, ent, sol = _ent_sol_module(tmp_path)
        _write(
            ent / "Ent.datamodel.yaml",
            "space: sp_ent\nexternalId: dm_ent\nversion: v1\n"
            "views:\n  - space: sp_ent\n    externalId: EntView\n    version: v1\n",
        )
        _write(ent / "EntView.view.yaml", "space: sp_ent\nexternalId: EntView\nversion: v1\nproperties: {}\n")
        _write(
            ent / "EntContainer.container.yaml",
            "space: sp_ent\nexternalId: EntContainer\n"
            "constraints:\n  needsBase:\n    require:\n      space: sp_ent\n"
            "      externalId: EntBase\n      type: container\n    constraintType: requires\n"
            "properties:\n  personRel:\n    type:\n      type: direct\n",
        )
        _write(
            ent / "EntBase.container.yaml",
            "space: sp_ent\nexternalId: EntBase\nproperties:\n  name:\n    type:\n      type: text\n",
        )
        _write(
            ent / "EntUnused.container.yaml",
            "space: sp_ent\nexternalId: EntUnused\nproperties:\n  name:\n    type:\n      type: text\n",
        )
        _write(ent / "sp_ent.Space.yaml", "space: sp_ent\nname: enterprise\n")
        _write(
            sol / "Sol.datamodel.yaml",
            "space: sp_sol\nexternalId: dm_sol\nversion: v1\n"
            "views:\n  - space: sp_sol\n    externalId: PobStay\n    version: v1\n"
            "  - space: sp_sol\n    externalId: Person\n    version: v1\n",
        )
        _write(
            sol / "PobStay.view.yaml",
            "space: sp_sol\nexternalId: PobStay\nversion: v1\n"
            "filter:\n  hasData:\n    - type: container\n      space: sp_ent\n"
            "      externalId: EntContainer\n"
            "properties:\n  personRel:\n    container:\n      space: sp_ent\n"
            "      externalId: EntContainer\n      type: container\n"
            "    containerPropertyIdentifier: personRel\n"
            "    source:\n      space: sp_sol\n      externalId: Person\n"
            "      version: v1\n      type: view\n",
        )
        _write(
            sol / "Person.view.yaml",
            "space: sp_sol\nexternalId: Person\nversion: v1\n"
            "properties:\n  pobStays:\n    connectionType: single_reverse_direct_relation\n"
            "    source:\n      space: sp_sol\n      externalId: PobStay\n"
            "      version: v1\n      type: view\n"
            "    through:\n      source:\n        space: sp_sol\n        externalId: PobStay\n"
            "        version: v1\n        type: view\n      identifier: personRel\n",
        )
        _write(sol / "sp_sol.Space.yaml", "space: sp_sol\nname: solution\n")

        schema = _import_schema(modeling, data_model_file="Sol.datamodel.yaml")
        assert schema.data_model.space == "sp_sol"
        assert {view.external_id for view in schema.views} == {"PobStay", "Person"}
        assert {container.external_id for container in schema.containers} == {"EntContainer", "EntBase"}
        assert {container.space for container in schema.containers} == {"sp_ent"}
        assert {space.space for space in schema.spaces} == {"sp_sol", "sp_ent"}
        assert "sp_ent" in schema.governed_space_set()

        orchestrator = _empty_orchestrator()
        orchestrator.run(schema)
        assert orchestrator.issues.by_code().get(ReverseConnectionContainerMissing.code, []) == []

    def test_container_ids_from_view_reads_mapping_not_view_sources(self) -> None:
        view = {
            "filter": {"hasData": [{"type": "container", "space": "sp_ent", "externalId": "E360PobStay"}]},
            "properties": {
                "personRel": {
                    "container": {"space": "sp_ent", "externalId": "E360PobStay", "type": "container"},
                    "source": {"space": "sp_sol", "externalId": "Person", "type": "view"},
                }
            },
        }
        assert DMSAPIImporter._container_ids_from_view(view) == {("sp_ent", "E360PobStay")}

    def test_repo_cdf_toml_does_not_hijack_unrelated_paths(self) -> None:
        assert find_toolkit_project_root(CYCLIC_REVERSE_ONLY) is None

    def test_substitute_unresolved_raises(self) -> None:
        with pytest.raises(FileReadException, match="Unresolved toolkit variable"):
            substitute_toolkit_variables("space: {{ missingVar }}", {}, source="test.yaml")

    def test_populate_toolkit_governed_spaces_respects_explicit_metadata(self) -> None:
        schema = RequestSchema(
            dataModel=DataModelRequest(space="dm_space", externalId="Model", version="v1", views=[]),
            extra=SchemaExtra(governedSpaces=[SpaceRequest(space="explicit_space")]),
        )
        updated = populate_toolkit_governed_spaces(schema)
        assert {space.space for space in updated.extra.governed_spaces} == {"explicit_space"}

    def test_import_validates_containers_in_derived_governed_spaces(self) -> None:
        schema = _import_schema(DATA_MODEL_DIR)
        orchestrator = DmsDataModelRulesOrchestrator(
            cdf_snapshot=SchemaSnapshot(
                data_model={},
                views={},
                containers={},
                spaces={},
                node_types={},
            ),
            limits=SchemaLimits(),
            modus_operandi="additive",
        )
        orchestrator.run(schema)

        enum_issues = orchestrator.issues.by_code().get(EnumerationMissingName.code, [])
        assert len(enum_issues) == 1
        assert "records_space:Record" in enum_issues[0].message
