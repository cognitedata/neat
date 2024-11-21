from typing import Any

import yaml
from cognite.client.data_classes.data_modeling import InstanceApply
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat._graph.loaders import DMSLoader
from cognite.neat._rules.exporters import YAMLExporter
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
    def test_classic_to_dms(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(storage="oxigraph")
        # Hack to read in the test data.
        for extractor in classic_windfarm.create_extractors():
            neat._state.instances.store.write(extractor)

        neat.prepare.instances.relationships_as_connections(limit=1)
        # Sequences is not yet supported
        neat.drop.instances("Sequence")

        neat.infer()

        # Hack to ensure deterministic output
        rules = neat._state.data_model.last_unverified_rule[1].rules
        rules.metadata.created = "2024-09-19T00:00:00Z"
        rules.metadata.updated = "2024-09-19T00:00:00Z"

        neat.prepare.data_model.prefix("Classic")

        neat.verify()

        neat.convert("dms")

        neat.mapping.classic_to_core(org_name=None)
        dms_rules = neat._state.data_model.last_verified_dms_rules
        store = neat._state.instances.store
        instances = [
            self._standardize_instance(instance)
            for instance in DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load()
        ]
        rules_str = YAMLExporter().export(dms_rules)

        rules_dict = yaml.safe_load(rules_str)

        data_regression.check({"rules": rules_dict, "instances": sorted(instances, key=lambda x: x["externalId"])})

    @staticmethod
    def _standardize_instance(instance: InstanceApply) -> dict[str, Any]:
        if not isinstance(instance, InstanceApply):
            raise ValueError(f"Expected InstanceApply, got {type(instance)}")
        for source in instance.sources:
            for value in source.properties.values():
                if isinstance(value, list):
                    value.sort()
        return instance.dump()
