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
from tests.data import classic_windfarm

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
    @pytest.mark.usefixtures("deterministic_uuid4")
    def test_classic_to_dms(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.
        for extractor in classic_windfarm.create_extractors():
            neat._state.instances.store.write(extractor)

        neat.prepare.instances.classic_to_core()

        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_unverified_rule
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"
        # Sorting the properties to ensure deterministic output
        rules.properties = sorted(rules.properties, key=lambda x: (x.class_, x.property_))

        neat.prepare.data_model.prefix("Classic")

        neat.verify()

        neat.prepare.data_model.add_implements_to_classes("Edge", "Edge")
        neat.convert("dms", mode="edge_properties")

        neat.mapping.data_model.classic_to_core("Classic", use_parent_property_name=True)

        neat.set.data_model_id(("sp_windfarm", "WindFarm", "v1"))

        # Hack to get the instances.
        dms_rules = neat._state.rule_store.last_verified_dms_rules
        store = neat._state.instances.store
        instances = [
            self._standardize_instance(instance)
            for instance in DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load()
            if isinstance(instance, InstanceApply)
        ]

        rules_str = neat.to.yaml(format="neat")

        neat.prepare.data_model.to_data_product(("sp_data_product", "DataProduct", "v1"))

        data_product_dict = yaml.safe_load(neat.to.yaml(format="neat"))

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
                "data_product": data_product_dict,
                "instances": sorted(instances, key=lambda x: x["externalId"]),
            }
        )

    def test_dexpi_to_dms(
        self, deterministic_uuid4: None, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.

        neat._state.instances.store.graph.parse(DATA_FOLDER / "dexpi-raw-graph.ttl")
        neat.prepare.instances.dexpi()
        neat.infer(max_number_of_instance=-1)

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_unverified_rule
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"

        neat.verify()

        neat.convert("dms")
        neat.set.data_model_id(("dexpi_playground", "DEXPI", "v1.3.1"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.rule_store.last_verified_dms_rules
            store = neat._state.instances.store
            instances = list(DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load())

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

    def test_aml_to_dms(
        self, deterministic_uuid4: None, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.

        neat._state.instances.store.graph.parse(DATA_FOLDER / "aml-raw-graph.ttl")
        neat.prepare.instances.aml()
        neat.infer(max_number_of_instance=-1)

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_unverified_rule
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"

        neat.verify()

        neat.convert("dms")
        neat.set.data_model_id(("aml_playground", "AML", "terminology_3.0"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.rule_store.last_verified_dms_rules
            store = neat._state.instances.store
            instances = list(DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load())

            nodes = [instance for instance in instances if isinstance(instance, NodeApply)]
            edges = [instance for instance in instances if isinstance(instance, EdgeApply)]
            instances = [
                self._standardize_instance(instance)
                for instance in DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load()
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

    def test_classic_to_cdf(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.
        for extractor in classic_windfarm.create_extractors():
            neat._state.instances.store.write(extractor)

        neat.prepare.instances.classic_to_core()

        neat.infer()

        neat.prepare.data_model.prefix("Classic")

        neat.verify()

        neat.prepare.data_model.add_implements_to_classes("Edge", "Edge")
        neat.convert("dms", mode="edge_properties")
        neat.mapping.data_model.classic_to_core("Classic")

        neat.set.data_model_id(("sp_windfarm", "WindFarm", "v1"))

        model_result = neat.to.cdf.data_model(existing="force")
        has_errors = {res.name: res.error_messages for res in model_result if res.error_messages}
        assert not has_errors, has_errors

        instance_result = neat.to.cdf.instances()
        has_errors = {res.name: res.error_messages for res in instance_result if res.error_messages}
        assert not has_errors, has_errors
