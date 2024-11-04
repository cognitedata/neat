from pathlib import Path
from typing import cast

import pytest
from cognite.client import data_modeling as dm

from cognite.neat._issues.warnings.user_modeling import DirectRelationMissingSourceWarning
from cognite.neat._rules.exporters import DMSExporter
from cognite.neat._rules.importers import DMSImporter, ExcelImporter
from cognite.neat._rules.models import DMSRules, DMSSchema, RoleTypes
from cognite.neat._rules.transformers import DMSToInformation, ImporterPipeline, VerifyDMSRules
from cognite.neat._utils.cdf.data_classes import ContainerApplyDict, SpaceApplyDict, ViewApplyDict
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
            "properties": {"__all__": {"reference"}},
            "reference": {"__all__"},
            "views": {"__all__": {"reference"}},
            # The Exporter adds node types for each view
            "nodes": {"__all__"},
        }
        args = dict(exclude_none=True, exclude_unset=True, exclude_defaults=True, exclude=exclude)
        dumped = rules.dump(**args)
        # The exclude above leaves an empty list for nodes, so we set it to None, to match the input.
        if not dumped.get("nodes"):
            dumped.pop("nodes", None)
        assert dumped == dms_rules.dump(**args)

    def test_import_rules_properties_with_edge_properties_units_and_enum(self) -> None:
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
        # The DMS Exporter dumps all node types, so we only check that the windturbine node type is present
        assert windturbine.NODE_TYPE.as_id() in dms_recreated.node_types

        assert (
            dms_recreated.containers[windturbine.WINDTURBINE_CONTAINER_ID].dump()
            == windturbine.WINDTURBINE_CONTAINER.dump()
        )
        assert dms_recreated.containers[windturbine.METMAST_CONTAINER_ID].dump() == windturbine.METMAST_CONTAINER.dump()
        assert (
            dms_recreated.containers[windturbine.DISTANCE_CONTAINER_ID].dump() == windturbine.DISTANCE_CONTAINER.dump()
        )

    def test_import_export_schema_with_inwards_edge_with_properties(self) -> None:
        importer = DMSImporter(SCHEMA_INWARDS_EDGE_WITH_PROPERTIES)

        result = ImporterPipeline.try_verify(importer)
        rules = cast(DMSRules, result.rules)
        issues = result.issues
        assert len(issues) == 0

        dms_recreated = DMSExporter().export(rules)

        assert dms_recreated.dump() == SCHEMA_INWARDS_EDGE_WITH_PROPERTIES.dump()


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
SCHEMA_INWARDS_EDGE_WITH_PROPERTIES = DMSSchema(
    data_model=dm.DataModelApply(
        space="neat",
        external_id="data_model",
        version="1",
        views=[
            dm.ViewId("neat", "NodeView1", "1"),
            dm.ViewId("neat", "NodeView2", "1"),
            dm.ViewId("neat", "EdgeView", "1"),
        ],
    ),
    spaces=SpaceApplyDict([dm.SpaceApply(space="neat")]),
    views=ViewApplyDict(
        [
            dm.ViewApply(
                space="neat",
                external_id="NodeView1",
                version="1",
                properties={
                    "to": dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference("neat", "myEdgeType"),
                        source=dm.ViewId("neat", "NodeView2", "v1"),
                        edge_source=dm.ViewId("neat", "EdgeView", "v1"),
                        direction="inwards",
                    )
                },
            ),
            dm.ViewApply(
                space="neat",
                external_id="NodeView2",
                version="1",
                properties={
                    "from": dm.MultiEdgeConnectionApply(
                        type=dm.DirectRelationReference("neat", "myEdgeType"),
                        source=dm.ViewId("neat", "NodeView1", "v1"),
                        edge_source=dm.ViewId("neat", "EdgeView", "v1"),
                        direction="outwards",
                    )
                },
            ),
            dm.ViewApply(
                space="neat",
                external_id="EdgeView",
                version="1",
                properties={
                    "distance": dm.MappedPropertyApply(
                        container=dm.ContainerId("neat", "container"),
                        container_property_identifier="distance",
                    )
                },
            ),
        ]
    ),
    containers=ContainerApplyDict(
        [
            dm.ContainerApply(
                space="neat",
                external_id="container",
                properties={
                    "distance": dm.ContainerProperty(
                        type=dm.data_types.Float64(),
                    )
                },
            )
        ]
    ),
)
