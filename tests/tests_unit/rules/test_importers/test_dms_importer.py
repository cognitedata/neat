from typing import cast

from cognite.client import data_modeling as dm

from cognite.neat.rules.importers import DMSImporter
from cognite.neat.rules.issues.importing import UnknownValueTypeWarning
from cognite.neat.rules.models.rules import DMSRules, DMSSchema


class TestDMSImporter:
    def test_import_with_direct_relation_none(self) -> None:
        importer = DMSImporter(SCHEMA_WITH_DIRECT_RELATION_NONE)

        rules, issues = importer.to_rules(errors="continue")

        assert len(issues) == 1
        assert issues[0] == UnknownValueTypeWarning("neat:OneView(version=1)", "direct")
        dms_rules = cast(DMSRules, rules)
        dump_dms = dms_rules.model_dump()
        assert dump_dms["properties"][0]["value_type"] == "#N/A"

        info_rules = dms_rules.as_information_architect_rules()
        dump_info = info_rules.model_dump()
        assert dump_info["properties"][0]["value_type"] == "#N/A"


SCHEMA_WITH_DIRECT_RELATION_NONE = DMSSchema()
SCHEMA_WITH_DIRECT_RELATION_NONE.spaces.append(dm.SpaceApply(space="neat"))
SCHEMA_WITH_DIRECT_RELATION_NONE.data_models.append(
    dm.DataModelApply(
        space="neat",
        external_id="data_model",
        version="0.1.0",
        views=[
            dm.ViewId("neat", "OneView", "1"),
        ],
    )
)
SCHEMA_WITH_DIRECT_RELATION_NONE.containers.append(
    dm.ContainerApply(
        space="neat",
        external_id="container",
        properties={
            "direct": dm.ContainerProperty(
                type=dm.DirectRelation(),
            )
        },
    )
)
SCHEMA_WITH_DIRECT_RELATION_NONE.views.append(
    dm.ViewApply(
        space="neat",
        external_id="OneView",
        version="1",
        properties={
            "direct": dm.MappedPropertyApply(
                container=dm.ContainerId("neat", "container"), container_property_identifier="direct", source=None
            )
        },
    )
)
