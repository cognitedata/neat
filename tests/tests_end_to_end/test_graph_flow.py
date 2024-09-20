from typing import Any

import yaml
from cognite.client.data_classes.data_modeling import InstanceApply
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.rules.exporters import YAMLExporter
from cognite.neat.rules.importers import InferenceImporter
from cognite.neat.rules.models.entities import UnknownEntity
from cognite.neat.rules.models.information import InformationInputProperty
from cognite.neat.rules.transformers import InformationToDMS, VerifyInformationRules
from cognite.neat.store import NeatGraphStore
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
        store = NeatGraphStore.from_oxi_store()
        for extractor in classic_windfarm.create_extractors():
            store.write(extractor)

        read_rules = InferenceImporter.from_graph_store(store, non_existing_node_type=UnknownEntity()).to_rules()
        # Ensure deterministic output
        read_rules.rules.metadata.created = "2024-09-19T00:00:00Z"
        read_rules.rules.metadata.updated = "2024-09-19T00:00:00Z"

        # We need to rename the classes to non-reserved names
        naming_mapping: dict[str, str] = {}
        for cls_ in read_rules.rules.classes:
            new_name = f"Classic{cls_.class_}"
            naming_mapping[cls_.class_] = new_name
            cls_.class_ = new_name

        # We need to filter out the DMS reserved properties from the rules
        new_properties: list[InformationInputProperty] = []
        for prop in read_rules.rules.properties:
            if prop.property_ not in RESERVED_PROPERTIES:
                prop.class_ = naming_mapping[prop.class_]
                new_properties.append(prop)
        read_rules.rules.properties = new_properties

        verified = VerifyInformationRules(errors="raise").transform(read_rules).get_rules()

        store.add_rules(verified)

        dms_rules = InformationToDMS().transform(verified).get_rules()

        instances = [
            self._standardize_instance(instance)
            for instance in DMSLoader.from_rules(dms_rules, store, "sp_instance_space").load()
        ]
        rules_str = YAMLExporter().export(dms_rules)

        rules_dict = yaml.safe_load(rules_str)

        data_regression.check({"rules": rules_dict, "instances": sorted(instances, key=lambda x: x["externalId"])})

    @staticmethod
    def _standardize_instance(instance: InstanceApply) -> dict[str, Any]:
        for source in instance.sources:
            for value in source.properties.values():
                if isinstance(value, list):
                    value.sort()
        return instance.dump()
