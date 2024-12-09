from typing import Any

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
from tests.utils import remove_linking_in_rules

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
    def test_classic_to_dms(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.
        for extractor in classic_windfarm.create_extractors():
            neat._state.instances.store.write(extractor)

        neat.prepare.instances.relationships_as_edges()
        # Sequences is not yet supported
        neat.drop.instances("Sequence")

        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.data_model.last_unverified_rule[1].rules
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"

        neat.prepare.data_model.prefix("Classic")

        neat.verify()

        neat.convert("dms", mode="edge_properties")

        neat.mapping.data_model.classic_to_core("Classic", use_parent_property_name=True)

        neat.set.data_model_id(("sp_windfarm", "WindFarm", "v1"))

        remove_linking_in_rules(neat._state.data_model.last_verified_dms_rules[1])

        rules_str = neat.to.yaml(format="neat")

        if False:
            # In progress, not yet supported.
            dms_rules = neat._state.data_model.last_verified_dms_rules[1]
            store = neat._state.instances.store
            instances = [
                self._standardize_instance(instance)
                for instance in DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load()
            ]
        else:
            instances = []
        rules_dict = yaml.safe_load(rules_str)
        data_regression.check({"rules": rules_dict, "instances": sorted(instances, key=lambda x: x["externalId"])})

    def test_dexpi_to_dms(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.

        neat._state.instances.store.graph.parse(DATA_FOLDER / "dexpi-raw-graph.ttl")
        neat.prepare.instances.dexpi()
        neat.infer(max_number_of_instance=-1)

        # Hack to ensure deterministic output
        rules = neat._state.data_model.last_unverified_rule[1].rules
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"

        neat.verify()

        neat.convert("dms")
        neat.set.data_model_id(("dexpi_playground", "DEXPI", "v1.3.1"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.data_model.last_verified_dms_rules[1]
            store = neat._state.instances.store
            instances = list(DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load())

            nodes = [instance for instance in instances if isinstance(instance, NodeApply)]
            edges = [instance for instance in instances if isinstance(instance, EdgeApply)]
        else:
            instances = []

        remove_linking_in_rules(neat._state.data_model.last_verified_dms_rules[1])
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
        neat = NeatSession(cognite_client, storage="oxigraph")
        # Hack to read in the test data.

        neat._state.instances.store.graph.parse(DATA_FOLDER / "aml-raw-graph.ttl")
        neat.prepare.instances.aml()
        neat.infer(max_number_of_instance=-1)

        # Hack to ensure deterministic output
        rules = neat._state.data_model.last_unverified_rule[1].rules
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"

        neat.verify()

        neat.convert("dms")
        neat.set.data_model_id(("aml_playground", "AML", "terminology_3.0"))

        if True:
            # In progress, not yet supported.
            dms_rules = neat._state.data_model.last_verified_dms_rules[1]
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

        remove_linking_in_rules(neat._state.data_model.last_verified_dms_rules[1])
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
        assert len(instances) == 206

    @staticmethod
    def _standardize_instance(instance: InstanceApply) -> dict[str, Any]:
        if not isinstance(instance, InstanceApply):
            raise ValueError(f"Expected InstanceApply, got {type(instance)}")
        for source in instance.sources:
            for value in source.properties.values():
                if isinstance(value, list) and all(isinstance(v, dict) for v in value):
                    value = sorted(value, key=lambda x: x["externalId"])
                elif isinstance(value, list):
                    value.sort()
        return instance.dump()
