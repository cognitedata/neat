from pathlib import Path
from typing import cast

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.issues.warnings.user_modeling import DirectRelationMissingSourceWarning
from cognite.neat.rules.exporters import DMSExporter
from cognite.neat.rules.importers import DMSImporter, ExcelImporter
from cognite.neat.rules.models import DMSRules, DMSSchema, RoleTypes
from cognite.neat.rules.transformers import DMSToInformation, ImporterPipeline, VerifyDMSRules
from tests.config import DOC_RULES
from tests.data import windturbine


class TestDMSImporter:
    def test_import_with_direct_relation_none(self) -> None:
        importer = DMSImporter(SCHEMA_WITH_DIRECT_RELATION_NONE)

        result = ImporterPipeline.try_verify(importer)
        rules = result.rules
        issues = result.issues
        assert len(issues) == 1
        assert issues[0] == DirectRelationMissingSourceWarning(dm.ViewId("neat", "OneView", "1"), "direct")
        dms_rules = cast(DMSRules, rules)
        dump_dms = dms_rules.dump()
        assert dump_dms["properties"][0]["value_type"] == "#N/A"
        assert dump_dms["properties"][0]["name"] == "direct"
        assert dump_dms["properties"][0]["description"] == "Direction Relation"
        assert dump_dms["views"][0]["name"] == "OneView"
        assert dump_dms["views"][0]["description"] == "One View"

        info_rules = DMSToInformation().transform(rules).rules
        dump_info = info_rules.dump()
        assert dump_info["properties"][0]["value_type"] == "#N/A"

    @pytest.mark.parametrize(
        "filepath",
        [
            pytest.param(DOC_RULES / "cdf-dms-architect-alice.xlsx", id="Alice rules"),
            pytest.param(DOC_RULES / "dms-analytics-olav.xlsx", id="Olav DMS rules"),
        ],
    )
    def test_import_rules_from_tutorials(self, filepath: Path) -> None:
        dms_rules = cast(DMSRules, ImporterPipeline.verify(ExcelImporter(filepath), role=RoleTypes.dms))
        # We must have the reference to be able to convert back to schema
        schema = dms_rules.as_schema()
        dms_importer = DMSImporter(schema)

        result = ImporterPipeline.try_verify(dms_importer)
        rules, issues = result.rules, result.issues
        issue_str = "\n".join([issue.as_message() for issue in issues])
        assert rules is not None, f"Failed to import rules {issue_str}"
        assert isinstance(rules, DMSRules)
        # This information is lost in the conversion to schema
        exclude = {
            "metadata": {"created", "updated"},
            "properties": {"data": {"__all__": {"reference"}}},
            "reference": {"__all__"},
            "views": {"data": {"__all__": {"reference"}}},
        }
        assert rules.dump(exclude=exclude) == dms_rules.dump(exclude=exclude)

    def test_import_rules_edge_with_properties(self) -> None:
        exporter = DMSImporter(windturbine.SCHEMA, metadata=windturbine.INPUT_RULES.metadata)

        result = exporter.to_rules()

        assert result.rules is not None
        assert result.rules.dump() == windturbine.INPUT_RULES.dump()

        rules = VerifyDMSRules(errors="raise").transform(result).get_rules()
        assert isinstance(rules, DMSRules)

        dms_recreated = DMSExporter().export(rules)
        # We cannot compare the whole schema, as the DMS Exporter makes things like
        # node types explicit along with filters. Thus, we compare selected parts
        turbine = windturbine.WIND_TURBINE.as_id()
        assert dms_recreated.views[turbine].dump()["properties"] == windturbine.WIND_TURBINE.dump()["properties"]
        metmast = windturbine.METMAST.as_id()
        assert dms_recreated.views[metmast].dump()["properties"] == windturbine.METMAST.dump()["properties"]


SCHEMA_WITH_DIRECT_RELATION_NONE = DMSSchema(
    data_model=dm.DataModelApply(
        space="neat",
        external_id="data_model",
        version="1",
        views=[
            dm.ViewId("neat", "OneView", "1"),
        ],
    )
)
SCHEMA_WITH_DIRECT_RELATION_NONE.spaces["neat"] = dm.SpaceApply(space="neat")
SCHEMA_WITH_DIRECT_RELATION_NONE.containers[dm.ContainerId("neat", "container")] = dm.ContainerApply(
    space="neat",
    external_id="container",
    properties={"direct": dm.ContainerProperty(type=dm.DirectRelation())},
)

SCHEMA_WITH_DIRECT_RELATION_NONE.views[dm.ViewId("neat", "OneView", "1")] = dm.ViewApply(
    space="neat",
    external_id="OneView",
    version="1",
    name="OneView",
    description="One View",
    properties={
        "direct": dm.MappedPropertyApply(
            container=dm.ContainerId("neat", "container"),
            container_property_identifier="direct",
            source=None,
            name="direct",
            description="Direction Relation",
        )
    },
)
