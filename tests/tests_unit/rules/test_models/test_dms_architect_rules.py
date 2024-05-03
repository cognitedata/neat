import datetime
from collections.abc import Iterable
from typing import Any

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm
from pydantic import ValidationError

import cognite.neat.rules.issues.spreadsheet
from cognite.neat.rules import issues as validation
from cognite.neat.rules.importers import DMSImporter
from cognite.neat.rules.models.data_types import String
from cognite.neat.rules.models.rules._base import ExtensionCategory, SchemaCompleteness, SheetList
from cognite.neat.rules.models.rules._dms_architect_rules import (
    DMSContainer,
    DMSProperty,
    DMSRules,
    DMSView,
)
from cognite.neat.rules.models.rules._dms_rules_write import (
    DMSContainerWrite,
    DMSMetadataWrite,
    DMSPropertyWrite,
    DMSRulesWrite,
    DMSViewWrite,
)
from cognite.neat.rules.models.rules._dms_schema import DMSSchema
from cognite.neat.rules.models.rules._information_rules import InformationRules


def rules_schema_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        DMSRulesWrite(
            metadata=DMSMetadataWrite(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                description="DMS data model",
                version="1",
                creator="Alice",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSPropertyWrite(
                    class_="WindTurbine",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSPropertyWrite(
                    class_="WindTurbine",
                    property_="ratedPower",
                    value_type="float64",
                    container="GeneratingUnit",
                    container_property="ratedPower",
                    view="WindTurbine",
                    view_property="ratedPower",
                ),
                DMSPropertyWrite(
                    class_="WindFarm",
                    property_="WindTurbines",
                    value_type="WindTurbine",
                    relation="multiedge",
                    view="WindFarm",
                    view_property="windTurbines",
                ),
            ],
            containers=[
                DMSContainerWrite(container="Asset", class_="Asset"),
                DMSContainerWrite(class_="GeneratingUnit", container="GeneratingUnit", constraint="Asset"),
            ],
            views=[
                DMSViewWrite("Asset"),
                DMSViewWrite(view="WindTurbine", implements="Asset"),
                DMSViewWrite(view="WindFarm"),
            ],
        ),
        DMSSchema(
            spaces=dm.SpaceApplyList(
                [
                    dm.SpaceApply(
                        space="my_space",
                    )
                ]
            ),
            data_models=dm.DataModelApplyList(
                [
                    dm.DataModelApply(
                        space="my_space",
                        external_id="my_data_model",
                        version="1",
                        description="DMS data model Creator: Alice",
                        views=[
                            dm.ViewId(space="my_space", external_id="Asset", version="1"),
                            dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                            dm.ViewId(space="my_space", external_id="WindFarm", version="1"),
                        ],
                    )
                ]
            ),
            views=dm.ViewApplyList(
                [
                    dm.ViewApply(
                        space="my_space",
                        external_id="Asset",
                        version="1",
                        properties={
                            "name": dm.MappedPropertyApply(
                                container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                            )
                        },
                        filter=dm.filters.HasData(
                            containers=[
                                dm.ContainerId("my_space", "Asset"),
                            ]
                        ),
                    ),
                    dm.ViewApply(
                        space="my_space",
                        external_id="WindTurbine",
                        version="1",
                        implements=[dm.ViewId("my_space", "Asset", "1")],
                        properties={
                            "ratedPower": dm.MappedPropertyApply(
                                container=dm.ContainerId("my_space", "GeneratingUnit"),
                                container_property_identifier="ratedPower",
                            ),
                        },
                        filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "GeneratingUnit")]),
                    ),
                    dm.ViewApply(
                        space="my_space",
                        external_id="WindFarm",
                        version="1",
                        properties={
                            "windTurbines": dm.MultiEdgeConnectionApply(
                                type=dm.DirectRelationReference(space="my_space", external_id="WindFarm.windTurbines"),
                                source=dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                                direction="outwards",
                            )
                        },
                        filter=dm.filters.Equals(
                            ["node", "type"],
                            {
                                "space": "my_space",
                                "externalId": "WindFarm",
                            },
                        ),
                    ),
                ]
            ),
            containers=dm.ContainerApplyList(
                [
                    dm.ContainerApply(
                        space="my_space",
                        external_id="Asset",
                        properties={"name": dm.ContainerProperty(type=dm.Text(), nullable=True)},
                    ),
                    dm.ContainerApply(
                        space="my_space",
                        external_id="GeneratingUnit",
                        properties={
                            "ratedPower": dm.ContainerProperty(type=dm.Float64(), nullable=True),
                        },
                        constraints={"my_space_Asset": dm.RequiresConstraint(dm.ContainerId("my_space", "Asset"))},
                    ),
                ]
            ),
            node_types=dm.NodeApplyList([dm.NodeApply(space="my_space", external_id="WindFarm")]),
        ),
        id="Two properties, one container, one view",
    )

    dms_rules = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-16T23:00:00",
            updated="2024-03-16T23:00:00",
            default_view_version="1",
        ),
        properties=[
            DMSPropertyWrite(
                class_="WindFarm",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="WindFarm",
                view_property="name",
            ),
            DMSPropertyWrite(
                class_="WindFarm",
                property_="windTurbines",
                value_type="WindTurbine",
                relation="direct",
                is_list=True,
                container="WindFarm",
                container_property="windTurbines",
                view="WindFarm",
                view_property="windTurbines",
            ),
            DMSPropertyWrite(
                class_="WindTurbine",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="WindTurbine",
                view_property="name",
            ),
        ],
        views=[
            DMSViewWrite(view="WindFarm", class_="WindFarm"),
            DMSViewWrite(view="WindTurbine", class_="WindTurbine"),
        ],
        containers=[
            DMSContainerWrite(container="Asset", class_="Asset"),
            DMSContainerWrite(class_="WindFarm", container="WindFarm", constraint="Asset"),
        ],
    )
    expected_schema = DMSSchema(
        spaces=dm.SpaceApplyList([dm.SpaceApply(space="my_space")]),
        data_models=dm.DataModelApplyList(
            [
                dm.DataModelApply(
                    space="my_space",
                    external_id="my_data_model",
                    version="1",
                    description="Creator: Anders",
                    views=[
                        dm.ViewId(space="my_space", external_id="WindFarm", version="1"),
                        dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                    ],
                )
            ]
        ),
        views=dm.ViewApplyList(
            [
                dm.ViewApply(
                    space="my_space",
                    external_id="WindFarm",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                        ),
                        "windTurbines": dm.MultiEdgeConnectionApply(
                            type=dm.DirectRelationReference(space="my_space", external_id="WindFarm.windTurbines"),
                            source=dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                            direction="outwards",
                        ),
                    },
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "Asset")]),
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="WindTurbine",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                        )
                    },
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "Asset")]),
                ),
            ]
        ),
        containers=dm.ContainerApplyList(
            [
                dm.ContainerApply(
                    space="my_space",
                    external_id="Asset",
                    properties={"name": dm.ContainerProperty(type=dm.Text(), nullable=True)},
                ),
            ]
        ),
        node_types=dm.NodeApplyList([]),
    )
    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Property with list of direct relations converted to multiedge",
    )

    dms_rules = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T08:30:00",
            updated="2024-03-17T08:30:00",
        ),
        properties=[
            DMSPropertyWrite(
                class_="Asset",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
            DMSPropertyWrite(
                class_="WindTurbine",
                property_="maxPower",
                value_type="float64",
                container="WindTurbine",
                container_property="maxPower",
                view="WindTurbine",
                view_property="maxPower",
            ),
        ],
        views=[
            DMSViewWrite(view="Asset", class_="Asset", in_model=False),
            DMSViewWrite(view="WindTurbine", class_="WindTurbine", implements="Asset"),
        ],
        containers=[
            DMSContainerWrite(container="Asset", class_="Asset"),
            DMSContainerWrite(class_="WindTurbine", container="WindTurbine", constraint="Asset"),
        ],
    )
    expected_schema = DMSSchema(
        spaces=dm.SpaceApplyList([dm.SpaceApply(space="my_space")]),
        data_models=dm.DataModelApplyList(
            [
                dm.DataModelApply(
                    space="my_space",
                    external_id="my_data_model",
                    version="1",
                    description="Creator: Anders",
                    views=[
                        dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                    ],
                )
            ]
        ),
        views=dm.ViewApplyList(
            [
                dm.ViewApply(
                    external_id="Asset",
                    space="my_space",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                        ),
                    },
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "Asset")]),
                ),
                dm.ViewApply(
                    external_id="WindTurbine",
                    space="my_space",
                    version="1",
                    properties={
                        "maxPower": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "WindTurbine"),
                            container_property_identifier="maxPower",
                        ),
                    },
                    implements=[dm.ViewId("my_space", "Asset", "1")],
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "WindTurbine")]),
                ),
            ],
        ),
        containers=dm.ContainerApplyList(
            [
                dm.ContainerApply(
                    space="my_space",
                    external_id="Asset",
                    properties={"name": dm.ContainerProperty(type=dm.Text(), nullable=True)},
                ),
                dm.ContainerApply(
                    space="my_space",
                    external_id="WindTurbine",
                    constraints={"my_space_Asset": dm.RequiresConstraint(dm.ContainerId("my_space", "Asset"))},
                    properties={"maxPower": dm.ContainerProperty(type=dm.Float64(), nullable=True)},
                ),
            ],
        ),
        node_types=dm.NodeApplyList([]),
    )

    yield pytest.param(
        dms_rules,
        expected_schema,
        id="View not in model",
    )

    dms_rules = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            # This is a complete schema, but we do not want to trigger the full validation
            schema_="partial",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T11:00:00",
            updated="2024-03-17T11:00:00",
            default_view_version="1",
        ),
        properties=[
            DMSPropertyWrite(
                class_="Asset",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
            DMSPropertyWrite(
                class_="Asset",
                property_="timeseries",
                value_type="Timeseries(property=asset)",
                relation="reversedirect",
                is_list=True,
                view="Asset",
                view_property="timeseries",
            ),
            DMSPropertyWrite(
                class_="Asset",
                property_="root",
                value_type="Asset",
                relation="direct",
                container="Asset",
                container_property="root",
                view="Asset",
                view_property="root",
            ),
            DMSPropertyWrite(
                class_="Asset",
                property_="children",
                value_type="Asset(property=root)",
                relation="reversedirect",
                is_list=True,
                view="Asset",
                view_property="children",
            ),
            DMSPropertyWrite(
                class_="Timeseries",
                property_="name",
                value_type="text",
                container="Timeseries",
                container_property="name",
                view="Timeseries",
                view_property="name",
            ),
            DMSPropertyWrite(
                class_="Timeseries",
                property_="asset",
                value_type="Asset",
                relation="direct",
                container="Timeseries",
                container_property="asset",
                view="Timeseries",
                view_property="asset",
            ),
            DMSPropertyWrite(
                class_="Timeseries",
                property_="activities",
                value_type="Activity",
                relation="direct",
                is_list=True,
                container="Timeseries",
                container_property="activities",
                view="Timeseries",
                view_property="activities",
            ),
            DMSPropertyWrite(
                class_="Activity",
                property_="timeseries",
                value_type="Timeseries(property=activities)",
                relation="reversedirect",
                view="Activity",
                view_property="timeseries",
            ),
        ],
        views=[
            DMSViewWrite(view="Asset", class_="Asset"),
            DMSViewWrite(view="Timeseries", class_="Timeseries"),
            DMSViewWrite(view="Activity", class_="Activity"),
        ],
        containers=[
            DMSContainerWrite(container="Asset", class_="Asset"),
            DMSContainerWrite(container="Timeseries", class_="Timeseries"),
            DMSContainerWrite(container="Activity", class_="Activity"),
        ],
    )

    expected_schema = DMSSchema(
        spaces=dm.SpaceApplyList([dm.SpaceApply(space="my_space")]),
        data_models=dm.DataModelApplyList(
            [
                dm.DataModelApply(
                    space="my_space",
                    external_id="my_data_model",
                    version="1",
                    description="Creator: Anders",
                    views=[
                        dm.ViewId(space="my_space", external_id="Asset", version="1"),
                        dm.ViewId(space="my_space", external_id="Timeseries", version="1"),
                        dm.ViewId(space="my_space", external_id="Activity", version="1"),
                    ],
                )
            ]
        ),
        views=dm.ViewApplyList(
            [
                dm.ViewApply(
                    space="my_space",
                    external_id="Asset",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                        ),
                        "timeseries": dm.MultiReverseDirectRelationApply(
                            source=dm.ViewId("my_space", "Timeseries", "1"),
                            through=dm.PropertyId(source=dm.ViewId("my_space", "Timeseries", "1"), property="asset"),
                        ),
                        "root": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"),
                            container_property_identifier="root",
                            source=dm.ViewId("my_space", "Asset", "1"),
                        ),
                        "children": dm.MultiReverseDirectRelationApply(
                            source=dm.ViewId("my_space", "Asset", "1"),
                            through=dm.PropertyId(source=dm.ViewId("my_space", "Asset", "1"), property="root"),
                        ),
                    },
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "Asset")]),
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="Timeseries",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Timeseries"), container_property_identifier="name"
                        ),
                        "asset": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Timeseries"),
                            container_property_identifier="asset",
                            source=dm.ViewId("my_space", "Asset", "1"),
                        ),
                        "activities": dm.MultiEdgeConnectionApply(
                            type=dm.DirectRelationReference(space="my_space", external_id="Timeseries.activities"),
                            source=dm.ViewId("my_space", "Activity", "1"),
                            direction="outwards",
                        ),
                    },
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "Timeseries")]),
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="Activity",
                    version="1",
                    properties={
                        "timeseries": dm.MultiEdgeConnectionApply(
                            type=dm.DirectRelationReference(space="my_space", external_id="Timeseries.activities"),
                            source=dm.ViewId("my_space", "Timeseries", "1"),
                            direction="inwards",
                        )
                    },
                    filter=dm.filters.Equals(
                        ["node", "type"],
                        {
                            "space": "my_space",
                            "externalId": "Activity",
                        },
                    ),
                ),
            ]
        ),
        containers=dm.ContainerApplyList(
            [
                dm.ContainerApply(
                    space="my_space",
                    external_id="Asset",
                    properties={
                        "name": dm.ContainerProperty(type=dm.Text(), nullable=True),
                        "root": dm.ContainerProperty(type=dm.DirectRelation(), nullable=True),
                    },
                ),
                dm.ContainerApply(
                    space="my_space",
                    external_id="Timeseries",
                    properties={
                        "name": dm.ContainerProperty(type=dm.Text(), nullable=True),
                        "asset": dm.ContainerProperty(type=dm.DirectRelation(), nullable=True),
                    },
                ),
            ]
        ),
        node_types=dm.NodeApplyList(
            [
                dm.NodeApply(space="my_space", external_id="Activity"),
            ]
        ),
    )
    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Multiple relations and reverse relations",
    )

    dms_rules = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T11:00:00",
            updated="2024-03-17T11:00:00",
            default_view_version="1",
        ),
        properties=[
            DMSPropertyWrite(
                class_="generating_unit",
                property_="display_name",
                value_type="text",
                container="generating_unit",
                container_property="display_name",
                view="generating_unit",
                view_property="display_name",
            )
        ],
        views=[
            DMSViewWrite(view="generating_unit", class_="generating_unit", filter_="NodeType(sp_other:wind_turbine)"),
        ],
        containers=[
            DMSContainerWrite(container="generating_unit", class_="generating_unit"),
        ],
    )

    expected_schema = DMSSchema(
        spaces=dm.SpaceApplyList([dm.SpaceApply(space="my_space")]),
        data_models=dm.DataModelApplyList(
            [
                dm.DataModelApply(
                    space="my_space",
                    external_id="my_data_model",
                    version="1",
                    description="Creator: Anders",
                    views=[
                        dm.ViewId(space="my_space", external_id="generating_unit", version="1"),
                    ],
                )
            ]
        ),
        views=dm.ViewApplyList(
            [
                dm.ViewApply(
                    space="my_space",
                    external_id="generating_unit",
                    version="1",
                    properties={
                        "display_name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "generating_unit"),
                            container_property_identifier="display_name",
                        ),
                    },
                    filter=dm.filters.Equals(["node", "type"], {"space": "sp_other", "externalId": "wind_turbine"}),
                ),
            ]
        ),
        containers=dm.ContainerApplyList(
            [
                dm.ContainerApply(
                    space="my_space",
                    external_id="generating_unit",
                    properties={"display_name": dm.ContainerProperty(type=dm.Text(), nullable=True)},
                ),
            ]
        ),
        node_types=dm.NodeApplyList([dm.NodeApply(space="sp_other", external_id="wind_turbine")]),
    )
    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Explict set NodeType Filter",
    )

    dms_rules = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            space="sp_solution",
            external_id="solution_model",
            version="1",
            creator="Bob",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSPropertyWrite(
                class_="Asset",
                property_="kinderen",
                value_type="Asset",
                relation="multiedge",
                reference="sp_enterprise:Asset(property=children)",
                view="Asset",
                view_property="kinderen",
            ),
        ],
        views=[
            DMSViewWrite(view="Asset", class_="Asset"),
        ],
    )

    expected_schema = DMSSchema(
        spaces=dm.SpaceApplyList(
            [
                dm.SpaceApply(space="sp_solution"),
            ]
        ),
        views=dm.ViewApplyList(
            [
                dm.ViewApply(
                    space="sp_solution",
                    external_id="Asset",
                    version="1",
                    properties={
                        "kinderen": dm.MultiEdgeConnectionApply(
                            type=dm.DirectRelationReference(
                                space="sp_enterprise",
                                external_id="Asset.children",
                            ),
                            source=dm.ViewId("sp_solution", "Asset", "1"),
                            direction="outwards",
                        ),
                    },
                    filter=dm.filters.Equals(["node", "type"], {"space": "sp_enterprise", "externalId": "Asset"}),
                ),
            ]
        ),
        data_models=dm.DataModelApplyList(
            [
                dm.DataModelApply(
                    space="sp_solution",
                    external_id="solution_model",
                    version="1",
                    description="Creator: Bob",
                    views=[
                        dm.ViewId(space="sp_solution", external_id="Asset", version="1"),
                    ],
                )
            ]
        ),
        node_types=dm.NodeApplyList([dm.NodeApply(space="sp_enterprise", external_id="Asset")]),
    )

    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Edge Reference to another data model",
    )


def valid_rules_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "name",
                        "value_type": "tEXt",
                        "container": "sp_core:Asset",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "name",
                    },
                    {
                        "class_": "WindTurbine",
                        "property_": "ratedPower",
                        "value_type": "float64",
                        "container": "GeneratingUnit",
                        "container_property": "ratedPower",
                        "view": "WindTurbine",
                        "view_property": "ratedPower",
                    },
                ]
            },
            "containers": {
                "data": [
                    {"class_": "Asset", "container": "sp_core:Asset"},
                    {
                        "class_": "GeneratingUnit",
                        "container": "GeneratingUnit",
                        "constraint": "sp_core:Asset",
                    },
                ]
            },
            "views": {
                "data": [
                    {"class_": "Asset", "view": "sp_core:Asset"},
                    {
                        "class_": "WindTurbine",
                        "view": "WindTurbine",
                        "implements": "sp_core:Asset",
                    },
                ]
            },
        },
        DMSRulesWrite(
            metadata=DMSMetadataWrite(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSPropertyWrite(
                    class_="WindTurbine",
                    property_="name",
                    value_type="text",
                    container="sp_core:Asset",
                    container_property="name",
                    view="sp_core:Asset(version=1)",
                    view_property="name",
                ),
                DMSPropertyWrite(
                    class_="WindTurbine",
                    property_="ratedPower",
                    value_type="float64",
                    container="GeneratingUnit",
                    container_property="ratedPower",
                    view="WindTurbine",
                    view_property="ratedPower",
                ),
            ],
            containers=[
                DMSContainerWrite(container="sp_core:Asset", class_="Asset"),
                DMSContainerWrite(class_="GeneratingUnit", container="GeneratingUnit", constraint="sp_core:Asset"),
            ],
            views=[
                DMSViewWrite(view="sp_core:Asset(version=1)"),
                DMSViewWrite(class_="WindTurbine", view="WindTurbine", implements="sp_core:Asset(version=1)"),
            ],
        ).as_read(),
        id="Two properties, two containers, two views. Primary data types, no relations.",
    )

    yield pytest.param(
        {
            "metadata": {
                "schema_": "complete",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "Plant",
                        "property_": "name",
                        "value_type": "text",
                        "container": "Asset",
                        "container_property": "name",
                        "view": "Asset",
                        "view_property": "name",
                    },
                    {
                        "class_": "Plant",
                        "property_": "generators",
                        "relation": "multiedge",
                        "value_type": "Generator",
                        "view": "Plant",
                        "view_property": "generators",
                    },
                    {
                        "class_": "Plant",
                        "property_": "reservoir",
                        "relation": "direct",
                        "value_type": "Reservoir",
                        "container": "Asset",
                        "container_property": "child",
                        "view": "Plant",
                        "view_property": "reservoir",
                    },
                    {
                        "class_": "Generator",
                        "property_": "name",
                        "value_type": "text",
                        "container": "Asset",
                        "container_property": "name",
                        "view": "Asset",
                        "view_property": "name",
                    },
                    {
                        "class_": "Reservoir",
                        "property_": "name",
                        "value_type": "text",
                        "container": "Asset",
                        "container_property": "name",
                        "view": "Asset",
                        "view_property": "name",
                    },
                ]
            },
            "containers": {
                "data": [
                    {"class_": "Asset", "container": "Asset"},
                    {
                        "class_": "Plant",
                        "container": "Plant",
                        "constraint": "Asset",
                    },
                ]
            },
            "views": {
                "data": [
                    {"class_": "Asset", "view": "Asset"},
                    {"class_": "Plant", "view": "Plant", "implements": "Asset"},
                    {"class_": "Generator", "view": "Generator", "implements": "Asset"},
                    {"class_": "Reservoir", "view": "Reservoir", "implements": "Asset"},
                ]
            },
        },
        DMSRulesWrite(
            metadata=DMSMetadataWrite(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSPropertyWrite(
                    class_="Plant",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSPropertyWrite(
                    class_="Plant",
                    property_="generators",
                    value_type="Generator",
                    relation="multiedge",
                    view="Plant",
                    view_property="generators",
                ),
                DMSPropertyWrite(
                    class_="Plant",
                    property_="reservoir",
                    value_type="Reservoir",
                    relation="direct",
                    container="Asset",
                    container_property="child",
                    view="Plant",
                    view_property="reservoir",
                ),
                DMSPropertyWrite(
                    class_="Generator",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSPropertyWrite(
                    class_="Reservoir",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
            ],
            containers=[
                DMSContainerWrite(container="Asset", class_="Asset"),
                DMSContainerWrite(class_="Plant", container="Plant", constraint="Asset"),
            ],
            views=[
                DMSViewWrite(view="Asset", class_="Asset"),
                DMSViewWrite(class_="Plant", view="Plant", implements="Asset"),
                DMSViewWrite(class_="Generator", view="Generator", implements="Asset"),
                DMSViewWrite(class_="Reservoir", view="Reservoir", implements="Asset"),
            ],
        ).as_read(),
        id="Five properties, two containers, four views. Direct relations and Multiedge.",
    )


def invalid_container_definitions_test_cases() -> Iterable[ParameterSet]:
    container_id = dm.ContainerId("my_space", "GeneratingUnit")
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "is_list": "false",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "maxPower",
                        "value_type": "float32",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        [
            cognite.neat.rules.issues.spreadsheet.MultiValueTypeError(
                container_id,
                "maxPower",
                {0, 1},
                {"float64", "float32"},
            )
        ],
        id="Inconsistent container definition value type",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "is_list": "true",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "is_list": "false",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        [
            cognite.neat.rules.issues.spreadsheet.MultiValueIsListError(
                container_id,
                "maxPower",
                {0, 1},
                {True, False},
            )
        ],
        id="Inconsistent container definition isList",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "nullable": "true",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "nullable": "false",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        [
            cognite.neat.rules.issues.spreadsheet.MultiNullableError(
                container_id,
                "maxPower",
                {0, 1},
                {True, False},
            )
        ],
        id="Inconsistent container definition nullable",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "index": "name",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "index": "name_index",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        [
            cognite.neat.rules.issues.spreadsheet.MultiIndexError(
                container_id,
                "name",
                {0, 1},
                {"name", "name_index"},
            )
        ],
        id="Inconsistent container definition index",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "constraint": "unique_name",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "constraint": "name",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        [
            cognite.neat.rules.issues.spreadsheet.MultiUniqueConstraintError(
                container_id,
                "name",
                {0, 1},
                {"unique_name", "name"},
            )
        ],
        id="Inconsistent container definition constraint",
    )


def invalid_extended_rules_test_cases() -> Iterable[ParameterSet]:
    ref_rules = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSPropertyWrite(
                class_="WindTurbine",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
        ],
        containers=[
            DMSContainerWrite(container="Asset", class_="Asset"),
        ],
        views=[
            DMSViewWrite(view="Asset", class_="Asset"),
        ],
    ).as_read()

    changing_container = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            extension="addition",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSPropertyWrite(
                class_="WindTurbine",
                property_="name",
                value_type="json",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
        ],
        containers=[
            DMSContainerWrite(container="Asset", class_="Asset"),
        ],
        views=[
            DMSViewWrite(view="Asset", class_="Asset"),
        ],
        reference=ref_rules,
    ).as_read()

    yield pytest.param(
        changing_container,
        [validation.dms.ChangingContainerError(dm.ContainerId("my_space", "Asset"), ["name"])],
        id="Addition extension, changing container",
    )

    changing_view = DMSRulesWrite(
        metadata=DMSMetadataWrite(
            schema_="complete",
            extension="addition",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSPropertyWrite(
                class_="WindTurbine",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="navn",
            ),
        ],
        containers=[
            DMSContainerWrite(container="Asset", class_="Asset"),
        ],
        views=[
            DMSViewWrite(view="Asset", class_="Asset"),
        ],
        reference=ref_rules,
    ).as_read()

    yield pytest.param(
        changing_view,
        [validation.dms.ChangingViewError(dm.ViewId("my_space", "Asset", "1"), ["navn"])],
        id="Addition extension, changing view",
    )

    changing_container2 = changing_container.model_copy(deep=True)
    changing_container2.metadata.extension = ExtensionCategory.reshape

    yield pytest.param(
        changing_container2,
        [validation.dms.ChangingContainerError(dm.ContainerId("my_space", "Asset"), ["name"])],
    )


class TestDMSRules:
    def test_load_valid_alice_rules(self, alice_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DMSRulesWrite.load(alice_spreadsheet).as_read()

        assert isinstance(valid_rules, DMSRules)

        sample_expected_properties = {
            "power:GeneratingUnit(version=0.1.0).name",
            "power:WindFarm(version=0.1.0).windTurbines",
            "power:Substation(version=0.1.0).mainTransformer",
        }
        missing = sample_expected_properties - {
            f"{prop.class_.versioned_id}.{prop.property_}" for prop in valid_rules.properties
        }
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("raw, expected_rules", list(valid_rules_tests_cases()))
    def test_load_valid_rules(self, raw: dict[str, dict[str, Any]], expected_rules: DMSRules) -> None:
        valid_rules = DMSRulesWrite.load(raw).as_read()
        assert valid_rules.model_dump() == expected_rules.model_dump()
        # testing case insensitive value types
        assert isinstance(valid_rules.properties.data[0].value_type, String)

    @pytest.mark.parametrize("raw, expected_errors", list(invalid_container_definitions_test_cases()))
    def test_load_inconsistent_container_definitions(
        self, raw: dict[str, dict[str, Any]], expected_errors: list[validation.NeatValidationError]
    ) -> None:
        with pytest.raises(ValueError) as e:
            DMSRulesWrite.load(raw).as_read()

        assert isinstance(e.value, ValidationError)
        validation_errors = e.value.errors()
        assert len(validation_errors) == 1, "Expected there to be exactly one validation error"
        validation_error = validation_errors[0]
        multi_value_error = validation_error.get("ctx", {}).get("error")
        assert isinstance(multi_value_error, validation.MultiValueError)
        actual_errors = multi_value_error.errors

        assert sorted(actual_errors) == sorted(expected_errors)

    def test_alice_to_and_from_DMS(self, alice_rules: DMSRules) -> None:
        schema = alice_rules.as_schema()
        rules = alice_rules.model_copy()
        recreated_rules = DMSImporter(schema).to_rules(errors="raise")

        # Sorting to avoid order differences
        recreated_rules.properties = SheetList[DMSProperty](
            data=sorted(recreated_rules.properties, key=lambda p: (p.class_, p.property_))
        )
        rules.properties = SheetList[DMSProperty](data=sorted(rules.properties, key=lambda p: (p.class_, p.property_)))
        recreated_rules.containers = SheetList[DMSContainer](
            data=sorted(recreated_rules.containers, key=lambda c: c.container)
        )
        rules.containers = SheetList[DMSContainer](data=sorted(rules.containers, key=lambda c: c.container))
        recreated_rules.views = SheetList[DMSView](data=sorted(recreated_rules.views, key=lambda v: v.view))
        rules.views = SheetList[DMSView](data=sorted(rules.views, key=lambda v: v.view))

        # Sorting out dates
        recreated_rules.metadata.created = rules.metadata.created
        recreated_rules.metadata.updated = rules.metadata.updated

        # Removing source which is lost in the conversion
        for prop in rules.properties:
            prop.reference = None

        assert recreated_rules.model_dump() == rules.model_dump()

    @pytest.mark.parametrize("input_rules, expected_schema", rules_schema_tests_cases())
    def test_as_schema(self, input_rules: DMSRulesWrite, expected_schema: DMSSchema) -> None:
        rules = input_rules.as_read()
        actual_schema = rules.as_schema()

        assert actual_schema.spaces.dump() == expected_schema.spaces.dump()
        actual_schema.data_models[0].views = sorted(actual_schema.data_models[0].views, key=lambda v: v.external_id)
        expected_schema.data_models[0].views = sorted(expected_schema.data_models[0].views, key=lambda v: v.external_id)
        assert actual_schema.data_models[0].dump() == expected_schema.data_models[0].dump()
        assert actual_schema.containers.dump() == expected_schema.containers.dump()

        actual_schema.views = dm.ViewApplyList(sorted(actual_schema.views, key=lambda v: v.external_id))
        expected_schema.views = dm.ViewApplyList(sorted(expected_schema.views, key=lambda v: v.external_id))
        assert actual_schema.views.dump() == expected_schema.views.dump()

        actual_schema.node_types = dm.NodeApplyList(sorted(actual_schema.node_types, key=lambda n: n.external_id))
        expected_schema.node_types = dm.NodeApplyList(sorted(expected_schema.node_types, key=lambda n: n.external_id))
        assert actual_schema.node_types.dump() == expected_schema.node_types.dump()

    def test_alice_as_information(self, alice_spreadsheet: dict[str, dict[str, Any]]) -> None:
        alice_rules = DMSRulesWrite.load(alice_spreadsheet).as_read()
        info_rules = alice_rules.as_information_architect_rules()

        assert isinstance(info_rules, InformationRules)

    def test_dump_skip_default_space_and_version(self) -> None:
        dms_rules = DMSRulesWrite(
            metadata=DMSMetadataWrite(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2024-03-16",
                updated="2024-03-16",
            ),
            properties=[
                DMSPropertyWrite(
                    class_="WindFarm",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="WindFarm",
                    view_property="name",
                ),
            ],
            views=[DMSViewWrite(view="WindFarm", class_="WindFarm", implements="Sourceable,Describable")],
            containers=[DMSContainerWrite(container="Asset", class_="Asset", constraint="Sourceable,Describable")],
        ).as_read()
        expected_dump = {
            "metadata": {
                "role": "DMS Architect",
                "schema_": SchemaCompleteness.partial,
                "space": "my_space",
                "external_id": "my_data_model",
                "creator": "Anders",
                "created": datetime.datetime(2024, 3, 16),
                "updated": datetime.datetime(2024, 3, 16),
                "version": "1",
                "default_view_version": "1",
            },
            "properties": [
                {
                    "class_": "WindFarm",
                    "property_": "name",
                    "value_type": "text",
                    "container": "Asset",
                    "container_property": "name",
                    "view": "WindFarm",
                    "view_property": "name",
                }
            ],
            "views": [{"view": "WindFarm", "class_": "WindFarm", "implements": "Sourceable,Describable"}],
            "containers": [{"container": "Asset", "class_": "Asset", "constraint": "Sourceable,Describable"}],
        }

        actual_dump = dms_rules.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=True)

        assert actual_dump == expected_dump

    def test_olav_as_information(self, olav_dms_rules: DMSRules) -> None:
        info_rules_copy = olav_dms_rules.model_copy(deep=True)
        # In Olav's Rules, the references are set for traceability. We remove it
        # to test that the references are correctly set in the conversion.
        for prop in info_rules_copy.properties:
            prop.reference = None
        for view in info_rules_copy.views:
            view.reference = None

        info_rules = olav_dms_rules.as_information_architect_rules()

        assert isinstance(info_rules, InformationRules)

        # Check some samples
        point = next((cls_ for cls_ in info_rules.classes if cls_.class_.versioned_id == "power_analytics:Point"), None)
        assert point is not None
        assert point.reference is not None
        assert point.reference.versioned_id == "power:Point"

        wind_turbine_name = next(
            (
                prop
                for prop in info_rules.properties
                if prop.property_ == "name" and prop.class_.versioned_id == "power_analytics:WindTurbine"
            ),
            None,
        )
        assert wind_turbine_name is not None
        assert wind_turbine_name.reference is not None
        assert wind_turbine_name.reference.versioned_id == "power:GeneratingUnit(property=name)"

    @pytest.mark.parametrize("rules, expected_issues", list(invalid_extended_rules_test_cases()))
    def test_load_invalid_extended_rules(self, rules: DMSRules, expected_issues: list[validation.ValidationIssue]):
        raw = rules.model_dump(by_alias=True)
        raw["Metadata"]["schema"] = "extended"

        with pytest.raises(ValidationError) as e:
            DMSRulesWrite.load(raw).as_read()

        actual_issues = validation.NeatValidationError.from_pydantic_errors(e.value.errors())

        assert sorted(actual_issues) == sorted(expected_issues)
