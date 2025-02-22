import datetime
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
from cognite.neat._graph.loaders import DMSLoader
from tests.config import DATA_FOLDER

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


class TestExtractToLoadFlow:
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

        neat.create.data_product_model(("sp_data_product", "DataProduct", "v1"))

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

    def test_uplift_workflow_to_cdf(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        neat.read.cdf._graph(
            ("sp_windfarm", "WindFarm", "v1"),
            instance_space=["sp_windfarm_dataset", "usecase_01", "source_ds", "maintenance"],
            unpack_json=True,
            str_to_ideal_type=True,
        )
        neat.infer()
        neat.set.data_model_id(("sp_windfarm_enterprise", "WindFarmEnterprise", "v1"))
        result = neat.to.cdf.data_model(existing="force")
        assert not any(res.error_messages for res in result)
        instance_result = neat.to.cdf._instances(use_source_space=True)
        errors = {res.name: res.error_messages for res in instance_result if res.error_messages}
        assert not errors, errors

    def test_dexpi_to_dms(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(cognite_client)
        neat.read.xml.dexpi(DATA_FOLDER / "depxi_example.xml")
        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_verified_information_rules
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        neat.convert()
        neat.set.data_model_id(("dexpi_playground", "DEXPI", "v1.3.1"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.rule_store.last_verified_dms_rules
            info_rules = neat._state.rule_store.last_verified_information_rules
            store = neat._state.instances.store
            instances = list(DMSLoader(dms_rules, info_rules, store, "sp_instance_space").load())

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
        neat.read.xml.aml(DATA_FOLDER / "aml_example.aml")
        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_verified_information_rules
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        neat.convert()
        neat.set.data_model_id(("aml_playground", "AML", "terminology_3.0"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.rule_store.last_verified_dms_rules
            info_rules = neat._state.rule_store.last_verified_information_rules
            store = neat._state.instances.store
            instances = list(DMSLoader(dms_rules, info_rules, store, "sp_instance_space").load())

            nodes = [instance for instance in instances if isinstance(instance, NodeApply)]
            edges = [instance for instance in instances if isinstance(instance, EdgeApply)]
            instances = [
                self._standardize_instance(instance)
                for instance in DMSLoader(dms_rules, info_rules, store, "sp_instance_space").load()
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
