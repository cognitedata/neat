from typing import Any

import yaml
from cognite.client.data_classes.data_modeling import InstanceApply
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat.graph.loaders import DMSLoader
from cognite.neat.rules.exporters import YAMLExporter
from cognite.neat.rules.importers import InferenceImporter
from cognite.neat.rules.models import SheetList
from cognite.neat.rules.models.entities import ClassEntity, UnknownEntity
from cognite.neat.rules.models.information import InformationProperty
from cognite.neat.rules.models.mapping import create_classic_to_core_mapping
from cognite.neat.rules.transformers import InformationToDMS, RuleMapper, VerifyInformationRules
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

        read_rules = InferenceImporter.from_graph_store(
            store, non_existing_node_type=UnknownEntity(), prefix="classic"
        ).to_rules()
        # Ensure deterministic output
        read_rules.rules.metadata.created = "2024-09-19T00:00:00Z"
        read_rules.rules.metadata.updated = "2024-09-19T00:00:00Z"

        verified = VerifyInformationRules(errors="raise").transform(read_rules).get_rules()

        mapped = RuleMapper(create_classic_to_core_mapping()).transform(verified).rules

        store.add_rules(mapped)

        # Manually remove duplicated property, up for discussion how to handle this.
        # It is caused by multiple sources being mapped to the same property.
        copy = mapped.model_copy(deep=True)
        seen: set[(ClassEntity, str)] = set()
        new_properties = SheetList[InformationProperty]()
        for prop in copy.properties:
            key = (prop.class_, prop.property_)
            if key in seen:
                continue
            seen.add(key)
            new_properties.append(prop)
        copy.properties = new_properties

        dms_rules = InformationToDMS().transform(copy).get_rules()

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
