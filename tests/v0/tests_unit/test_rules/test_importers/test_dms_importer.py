from pathlib import Path
from typing import cast

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.v0.core._client.data_classes.data_modeling import (
    ContainerApplyDict,
    SpaceApplyDict,
    ViewApplyDict,
)
from cognite.neat.v0.core._data_model.exporters import DMSExporter
from cognite.neat.v0.core._data_model.importers import DMSImporter, ExcelImporter
from cognite.neat.v0.core._data_model.models import DMSSchema, PhysicalDataModel
from cognite.neat.v0.core._data_model.transformers import (
    PhysicalToConceptual,
    VerifyPhysicalDataModel,
)
from cognite.neat.v0.core._issues import catch_issues
from cognite.neat.v0.core._issues.warnings.user_modeling import (
    DirectRelationMissingSourceWarning,
)
from tests.v0.config import DOC_RULES
from tests.v0.data import SchemaData


class TestDMSImporter:
    def test_import_with_direct_relation_none(self) -> None:
        importer = DMSImporter(SCHEMA_WITH_DIRECT_RELATION_NONE)

        with catch_issues() as issues:
            rules = VerifyPhysicalDataModel().transform(importer.to_data_model())
        assert len(issues) == 1
        dms_rules = cast(PhysicalDataModel, rules)
        dump_dms = dms_rules.dump()
        assert dump_dms["properties"][0]["value_type"] == "#N/A"
        assert dump_dms["properties"][0]["name"] == "direct"
        assert dump_dms["properties"][0]["description"] == "Direction Relation"
        assert dump_dms["views"][0]["name"] == "OneView"
        assert dump_dms["views"][0]["description"] == "One View"

        info_rules = PhysicalToConceptual().transform(rules)
        dump_info = info_rules.dump()
        assert dump_info["properties"][0]["value_type"] == "#N/A"

    @pytest.mark.parametrize(
        "filepath",
        [
            pytest.param(DOC_RULES / "cdf-dms-architect-alice.xlsx", id="Alice rules"),
        ],
    )
    def test_import_rules_from_tutorials(self, filepath: Path) -> None:
        dms_rules = ExcelImporter(filepath).to_data_model().unverified_data_model.as_verified_data_model()
        # We must have the reference to be able to convert back to schema
        schema = dms_rules.as_schema()
        dms_importer = DMSImporter(schema)

        with catch_issues() as issues:
            rules = VerifyPhysicalDataModel().transform(dms_importer.to_data_model())

        issue_str = "\n".join([issue.as_message() for issue in issues])
        assert rules is not None, f"Failed to import rules {issue_str}"
        assert isinstance(rules, PhysicalDataModel)
        # This information is lost in the conversion to schema
        exclude = {
            "metadata": {"created", "updated"},
            "properties": {"__all__": {"reference", "neatId"}},
            "containers": {"__all__": {"neatId"}},
            "reference": {"__all__"},
            "views": {"__all__": {"reference", "neatId"}},
            # The Exporter adds node types for each view
            "nodes": {"__all__"},
        }
        args = dict(exclude_none=True, sort=True, exclude_unset=True, exclude_defaults=True, exclude=exclude)
        dumped = rules.dump(**args)
        # The exclude above leaves an empty list for nodes, so we set it to None, to match the input.
        if not dumped.get("nodes"):
            dumped.pop("nodes", None)
        assert dumped == dms_rules.dump(**args)

    def test_import_rules_properties_with_edge_properties_units_and_enum(self) -> None:
        windturbine = SchemaData.NonNeatFormats.windturbine
        exporter = DMSImporter(windturbine.SCHEMA, metadata=windturbine.INPUT_RULES.metadata)

        result = exporter.to_data_model()

        assert result.unverified_data_model is not None
        assert result.unverified_data_model.dump() == windturbine.INPUT_RULES.dump()

        rules = VerifyPhysicalDataModel().transform(result)
        assert isinstance(rules, PhysicalDataModel)

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

        rules = importer.to_data_model().unverified_data_model.as_verified_data_model()

        dms_recreated = DMSExporter().export(rules)

        assert dms_recreated.views.dump() == SCHEMA_INWARDS_EDGE_WITH_PROPERTIES.views.dump()

    def test_import_schema_with_referenced_enum(self) -> None:
        importer = DMSImporter(
            SCHEMA_WITH_REFERENCED_ENUM,
            referenced_containers=[
                dm.ContainerApply(
                    space="cdf_cdm",
                    external_id="CogniteTimeSeries",
                    properties={
                        "type": dm.ContainerProperty(
                            type=dm.data_types.Enum(
                                {
                                    "numeric": dm.data_types.EnumValue(),
                                    "string": dm.data_types.EnumValue(),
                                }
                            )
                        )
                    },
                )
            ],
        )

        with catch_issues() as issues:
            _ = importer.to_data_model()

        assert len(issues) == 0

    def test_import_schema_with_multi_value_hack(self) -> None:
        importer = DMSImporter(SCHEMA_WITH_MULTI_VALUE_HACK)

        dms_rules: PhysicalDataModel | None = None
        with catch_issues() as issues:
            input_rules = importer.to_data_model()
            dms_rules = VerifyPhysicalDataModel(validate=True, client=None).transform(input_rules)

        assert sorted(issues) == [
            DirectRelationMissingSourceWarning(dm.ViewId("neat", "DirectRelationView", "1"), "direct")
        ]
        assert isinstance(dms_rules, PhysicalDataModel)


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
        description="Creator: MISSING",
        views=[
            dm.ViewId("neat", "EdgeView", "1"),
            dm.ViewId("neat", "NodeView1", "1"),
            dm.ViewId("neat", "NodeView2", "1"),
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
                        source=dm.ViewId("neat", "NodeView2", "1"),
                        edge_source=dm.ViewId("neat", "EdgeView", "1"),
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
                        source=dm.ViewId("neat", "NodeView1", "1"),
                        edge_source=dm.ViewId("neat", "EdgeView", "1"),
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

SCHEMA_WITH_REFERENCED_ENUM = DMSSchema(
    data_model=dm.DataModelApply(
        space="neat",
        external_id="data_model",
        version="v1",
        views=[
            dm.ViewId("neat", "OneView", "v1"),
        ],
    ),
    spaces=SpaceApplyDict([dm.SpaceApply(space="neat")]),
    views=ViewApplyDict(
        [
            dm.ViewApply(
                space="neat",
                external_id="OneView",
                version="1",
                properties={
                    "type": dm.MappedPropertyApply(
                        container=dm.ContainerId("cdf_cdm", "CogniteTimeSeries"),
                        container_property_identifier="type",
                    )
                },
            )
        ]
    ),
)


# We have users that sets direct relations property.source to None, and have
# reverse direct relation through this direct relation to get a multi-value behavior in Search.
SCHEMA_WITH_MULTI_VALUE_HACK = DMSSchema(
    data_model=dm.DataModelApply(
        space="neat",
        external_id="data_model",
        version="1",
        views=[
            dm.ViewId("neat", "DirectRelationView", "1"),
            dm.ViewId("neat", "ReverseView1", "1"),
            dm.ViewId("neat", "ReverseView2", "1"),
        ],
    ),
    spaces=SpaceApplyDict([dm.SpaceApply(space="neat")]),
    views=ViewApplyDict(
        [
            dm.ViewApply(
                space="neat",
                external_id="DirectRelationView",
                version="1",
                properties={
                    "direct": dm.MappedPropertyApply(
                        container=dm.ContainerId("neat", "container"),
                        container_property_identifier="direct",
                        source=None,
                        name="direct",
                        description="Direction Relation",
                    )
                },
            ),
            dm.ViewApply(
                space="neat",
                external_id="ReverseView1",
                version="1",
                properties={
                    "reverse1": dm.MultiReverseDirectRelationApply(
                        source=dm.ViewId("neat", "DirectRelationView", "1"),
                        through=dm.PropertyId(dm.ViewId("neat", "DirectRelationView", "1"), "direct"),
                    ),
                },
            ),
            dm.ViewApply(
                space="neat",
                external_id="ReverseView2",
                version="1",
                properties={
                    "reverse2": dm.MultiReverseDirectRelationApply(
                        source=dm.ViewId("neat", "DirectRelationView", "1"),
                        through=dm.PropertyId(dm.ViewId("neat", "DirectRelationView", "1"), "direct"),
                    ),
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
                    "direct": dm.ContainerProperty(type=dm.DirectRelation()),
                },
            )
        ]
    ),
)
