import datetime
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
import yaml
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import (
    EdgeApply,
    InstanceApply,
    NodeApply,
)
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat.v0.core._constants import COGNITE_SPACES
from cognite.neat.v0.core._data_model.models.entities import ContainerEntity
from cognite.neat.v0.core._instances.loaders import DMSLoader, InstanceSpaceLoader
from tests.v0.data import GraphData, SchemaData

RESERVED_PROPERTIES = frozenset(
    {
        "created_time",
        "deleted_time",
        "edge_id",
        "extensions",
        "external_id",
        "last_updated_time",
        "node_id",
        "project-id",
        "project_group",
        "seq",
        "space",
        "version",
        "tg_table_name",
        "start_node",
        "end_node",
    }
)


@pytest.mark.skip(reason="Legacy tests which we no longer maintain")
class TestExtractToLoadFlow:
    def test_snapshot_workflow_ids_to_python(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        issues = neat.read.cdf.classic.graph("Utsira", identifier="id")
        assert not issues.has_errors
        issues = neat.convert()
        assert not issues.has_errors
        issues = neat.mapping.data_model.classic_to_core("Classic")
        assert not issues.has_errors
        neat.set.data_model_id(("sp_windfarm", "WindFarm", "v1"), name="Nikola is NEAT janitor")
        instances, issues = neat.to._python.instances(
            "sp_windfarm_dataset",
            space_from_property="dataSetId",
        )
        assert not issues.has_errors
        rules_str = neat.to.yaml(format="neat")
        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
                "instances": sorted(
                    [self._standardize_instance(node) for node in instances], key=lambda x: x["externalId"]
                ),
            }
        )

    def test_snapshot_workflow_to_python(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        issues = neat.read.cdf.classic.graph("Utsira", identifier="externalId")
        assert not issues.has_errors
        issues = neat.convert()
        assert not issues.has_errors
        issues = neat.mapping.data_model.classic_to_core("Classic")
        assert not issues.has_errors
        neat.set.data_model_id(("sp_windfarm", "WindFarm", "v1"))
        instances, issues = neat.to._python.instances("sp_windfarm_dataset", space_from_property="dataSetId")
        assert not issues.has_errors

        rules_str = neat.to.yaml(format="neat")

        neat.template.data_product_model(("sp_data_product", "DataProduct", "v1"))

        data_product_dict = yaml.safe_load(neat.to.yaml(format="neat"))

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
                "data_product": data_product_dict,
                "instances": sorted(
                    [self._standardize_instance(node) for node in instances], key=lambda x: x["externalId"]
                ),
            }
        )

    def test_snapshot_workflow_to_cdf(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        neat.read.cdf.classic.graph("Utsira", identifier="externalId")
        neat.convert()
        neat.mapping.data_model.classic_to_core("NeatInc")
        neat.set.data_model_id(("sp_windfarm", "WindFarm", "v1"))

        model_result = neat.to.cdf.data_model(existing="force")
        has_errors = {res.name: res.error_messages for res in model_result if res.error_messages}
        assert not has_errors, has_errors

        instance_result = neat.to.cdf.instances("sp_windfarm_dataset", space_property="dataSetId")
        has_errors = {res.name: res.error_messages for res in instance_result if res.error_messages}
        assert not has_errors, has_errors

    @pytest.mark.skip("Skipping test as it is being worked on other branch")
    def test_uplift_workflow_to_python(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        neat.read.cdf._graph(
            ("sp_windfarm", "WindFarm", "v1"),
            instance_space=["sp_windfarm_dataset", "usecase_01", "source_ds", "maintenance"],
            unpack_json=True,
            str_to_ideal_type=True,
        )
        issues = neat.infer()
        assert not issues.has_errors
        neat.set.data_model_id(("sp_windfarm_enterprise", "WindFarmEnterprise", "v1"))
        instances, issues = neat.to._python.instances(use_source_space=True)
        assert not issues.has_errors
        rules_str = neat.to.yaml(format="neat")
        data_regression.check(
            {
                "rules": yaml.safe_load(rules_str),
                "instances": sorted(
                    [self._standardize_instance(node) for node in instances], key=lambda x: x["externalId"]
                ),
            }
        )

    @pytest.mark.skip("Skipping test as it has tendecy to clash with other tests")
    def test_uplift_workflow_to_cdf(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        neat.read.cdf._graph(
            ("sp_windfarm", "WindFarm", "v1"),
            instance_space=["sp_windfarm_dataset", "usecase_01", "source_ds", "maintenance"],
            unpack_json=True,
            str_to_ideal_type=True,
        )
        issues = neat.infer()
        assert not issues.has_errors
        neat.set.data_model_id(("sp_windfarm_enterprise", "WindFarmEnterprise", "v1"))
        result = neat.to.cdf.data_model(existing="force")
        assert not any(res.error_messages for res in result)
        instance_result = neat.to.cdf._instances(use_source_space=True)
        errors = {res.name: res.error_messages for res in instance_result if res.error_messages}
        assert not errors, errors

    def test_no_node_type_on_system_views_instances(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        neat.read.cdf._graph(
            ("sp_windfarm", "WindFarm", "v1"),
            instance_space=["sp_windfarm_dataset", "usecase_01", "source_ds", "maintenance"],
            unpack_json=True,
            str_to_ideal_type=True,
            skip_cognite_views=False,
        )
        instances, _ = neat.to._python.instances(use_source_space=True)

        check = []
        for instance in instances:
            if instance.instance_type == "node" and instance.sources[0].source.space in COGNITE_SPACES:
                check.append(instance.type is None)

        assert all(check), "System views should not have node type"

    def test_convert_info_with_cdm_ref(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        neat.read.excel(SchemaData.Conceptual.info_with_cdm_ref_xlsx)
        issues = neat.convert()
        assert not issues.has_errors

        dms = neat._state.data_model_store.last_verified_physical_data_model

        expected_containers = {
            ContainerEntity(space="cdf_cdm", externalId="CogniteAsset"),
            ContainerEntity(space="cdf_cdm", externalId="CogniteDescribable"),
            ContainerEntity(space="cdf_cdm", externalId="CogniteSourceable"),
            ContainerEntity(space="cdf_cdm", externalId="CogniteVisualizable"),
            ContainerEntity(space="cdf_cdm", externalId="CogniteSchedulable"),
            ContainerEntity(space="cdf_cdm", externalId="CogniteActivity"),
        }
        actual_containers = {c.container for c in dms.containers or []}
        assert expected_containers <= actual_containers, (
            f"Expected {expected_containers} to be a subset of {actual_containers}"
        )
        properties_by_external_id = defaultdict(set)
        value_type_by_property: dict[tuple[str, str], str] = {}
        description_by_property: dict[tuple[str, str], str] = {}
        for prop in dms.properties:
            properties_by_external_id[prop.view.external_id].add(prop.view_property)
            value_type_by_property[(prop.view.external_id, prop.view_property)] = str(prop.value_type)
            description_by_property[(prop.view.external_id, prop.view_property)] = prop.description

        assert "WindTurbine" in properties_by_external_id
        assert "WorkOrder" in properties_by_external_id

        assert "maxCapacity" in properties_by_external_id["WindTurbine"], "Missing custom property 'maxCapacity'"
        updated_description = description_by_property.get(("WindTurbine", "name"))
        assert updated_description == "This is an updated description of name."
        assert value_type_by_property.get(("WindTurbine", "activities")) == "my_space:WorkOrder(version=v1)"
        assert value_type_by_property.get(("WorkOrder", "assets")) == "my_space:WindTurbine(version=v1)"

    def test_dexpi_to_dms(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(cognite_client)
        neat.read.xml.dexpi(GraphData.dexpi_example_xml)
        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.data_model_store.last_verified_conceptual_data_model
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        neat.convert()
        neat.set.data_model_id(("dexpi_playground", "DEXPI", "v1.3.1"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.data_model_store.last_verified_physical_data_model
            info_rules = neat._state.data_model_store.last_verified_conceptual_data_model
            store = neat._state.instances.store
            instance_loader = InstanceSpaceLoader(instance_space="sp_instance_space")
            instances = list(DMSLoader(dms_rules, info_rules, store, instance_loader.space_by_instance_uri).load())

            nodes = [instance for instance in instances if isinstance(instance, NodeApply)]
            edges = [instance for instance in instances if isinstance(instance, EdgeApply)]
        else:
            instances = []

        rules_str = neat.to.yaml(format="neat")

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
                "instances": [],
            }
        )

        assert len(nodes) == 206
        assert len(edges) == 40

    def test_aml_to_dms(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(cognite_client)
        neat.read.xml.aml(GraphData.aml_example_aml)
        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.data_model_store.last_verified_conceptual_data_model
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        neat.convert()
        neat.set.data_model_id(("aml_playground", "AML", "terminology_3.0"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.data_model_store.last_verified_physical_data_model
            info_rules = neat._state.data_model_store.last_verified_conceptual_data_model
            store = neat._state.instances.store
            instance_loader = InstanceSpaceLoader(instance_space="sp_instance_space")
            instances = list(DMSLoader(dms_rules, info_rules, store, instance_loader.space_by_instance_uri).load())

            nodes = [instance for instance in instances if isinstance(instance, NodeApply)]
            edges = [instance for instance in instances if isinstance(instance, EdgeApply)]
            instances = [
                self._standardize_instance(instance)
                for instance in DMSLoader(dms_rules, info_rules, store, instance_loader.space_by_instance_uri).load()
            ]

        else:
            instances = []

        rules_str = neat.to.yaml(format="neat")

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
                "instances": [],
            }
        )

        assert len(nodes) == 973
        assert len(edges) == 972
        assert len(instances) == 1945

    def test_create_extension_template(
        self, cognite_client: CogniteClient, tmp_path: Path, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)
        output_path = tmp_path / "extension_template.xlsx"
        neat.template.expand(SchemaData.Conceptual.only_concepts_xlsx, output_path)
        assert output_path.exists()
        neat.read.excel(output_path)

        model_str = neat.to.yaml(format="neat")

        model_dict = yaml.safe_load(model_str)

        data_regression.check(model_dict)

    def test_create_extension_template_broken(
        self, cognite_client: CogniteClient, tmp_path: Path, data_regression: DataRegressionFixture
    ) -> None:
        """
        Test to validate the behavior when field is invalid in the Excel sheet. # noqa
        The broken_concepts.xlsx example has only one property, which is invalid.
        Neat should inform the end user what/where is the  when using neat.inspect
        """

        neat = NeatSession(cognite_client)
        output_path = tmp_path / "extension_template_broken.xlsx"
        neat.template.expand(SchemaData.Conceptual.broken_concepts_xlsx, output_path)

        error = neat.inspect.issues()

        assert error["NeatIssue"][0] == "PropertyValueError"

    @staticmethod
    def _standardize_instance(instance: InstanceApply) -> dict[str, Any]:
        if not isinstance(instance, InstanceApply):
            raise ValueError(f"Expected InstanceApply, got {type(instance)}")

        def dict_sort(v: dict[str, Any]) -> str:
            for key in ["externalId", "rowNumber", "colNumber"]:
                if key in v:
                    return v[key]
            return str(v)

        for source in instance.sources:
            for value in source.properties.values():
                if isinstance(value, list) and all(isinstance(v, dict) for v in value):
                    value.sort(key=dict_sort)
                elif isinstance(value, list):
                    value.sort()
        return instance.dump()
