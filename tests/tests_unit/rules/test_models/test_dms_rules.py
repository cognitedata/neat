import dataclasses
import datetime
from collections.abc import Iterable
from typing import Any

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm
from pydantic import ValidationError

from cognite.neat.issues import MultiValueError, NeatError, NeatIssue
from cognite.neat.issues.errors import (
    PropertyDefinitionDuplicatedError,
    ResourceChangedError,
    ResourceNotFoundError,
)
from cognite.neat.rules.importers import DMSImporter
from cognite.neat.rules.models import DMSRules, InformationRules
from cognite.neat.rules.models.data_types import String
from cognite.neat.rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
    DMSSchema,
)
from cognite.neat.rules.models.entities._single_value import UnknownEntity
from cognite.neat.rules.transformers import (
    DMSToInformation,
    ImporterPipeline,
    InformationToDMS,
    MapOneToOne,
    RulesPipeline,
)
from cognite.neat.utils.cdf.data_classes import ContainerApplyDict, NodeApplyDict, SpaceApplyDict, ViewApplyDict
from tests.data import car


def rules_schema_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
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
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="ratedPower",
                    value_type="float64",
                    container="GeneratingUnit",
                    container_property="ratedPower",
                    view="WindTurbine",
                    view_property="ratedPower",
                ),
                DMSInputProperty(
                    class_="WindFarm",
                    property_="WindTurbines",
                    value_type="WindTurbine",
                    connection="edge",
                    view="WindFarm",
                    view_property="windTurbines",
                ),
            ],
            containers=[
                DMSInputContainer(container="Asset", class_="Asset"),
                DMSInputContainer(class_="GeneratingUnit", container="GeneratingUnit", constraint="Asset"),
            ],
            views=[
                DMSInputView("Asset"),
                DMSInputView(view="WindTurbine", implements="Asset"),
                DMSInputView(view="WindFarm"),
            ],
        ),
        DMSSchema(
            spaces=SpaceApplyDict(
                [
                    dm.SpaceApply(
                        space="my_space",
                    )
                ]
            ),
            data_model=dm.DataModelApply(
                space="my_space",
                external_id="my_data_model",
                version="1",
                description="DMS data model Creator: Alice",
                views=[
                    dm.ViewId(space="my_space", external_id="Asset", version="1"),
                    dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                    dm.ViewId(space="my_space", external_id="WindFarm", version="1"),
                ],
            ),
            views=ViewApplyDict(
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
            containers=ContainerApplyDict(
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
            node_types=NodeApplyDict([dm.NodeApply(space="my_space", external_id="WindFarm")]),
        ),
        id="Two properties, one container, one view",
    )

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-16T23:00:00",
            updated="2024-03-16T23:00:00",
        ),
        properties=[
            DMSInputProperty(
                class_="WindFarm",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="WindFarm",
                view_property="name",
            ),
            DMSInputProperty(
                class_="WindFarm",
                property_="windTurbines",
                value_type="WindTurbine",
                connection="direct",
                is_list=True,
                container="WindFarm",
                container_property="windTurbines",
                view="WindFarm",
                view_property="windTurbines",
            ),
            DMSInputProperty(
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
            DMSInputView(view="WindFarm", class_="WindFarm"),
            DMSInputView(view="WindTurbine", class_="WindTurbine"),
        ],
        containers=[
            DMSInputContainer(container="Asset", class_="Asset"),
            DMSInputContainer(class_="WindFarm", container="WindFarm", constraint="Asset"),
        ],
    )
    expected_schema = DMSSchema(
        spaces=SpaceApplyDict([dm.SpaceApply(space="my_space")]),
        data_model=dm.DataModelApply(
            space="my_space",
            external_id="my_data_model",
            version="1",
            description="Creator: Anders",
            views=[
                dm.ViewId(space="my_space", external_id="WindFarm", version="1"),
                dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
            ],
        ),
        views=ViewApplyDict(
            [
                dm.ViewApply(
                    space="my_space",
                    external_id="WindFarm",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                        ),
                        "windTurbines": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "WindFarm"),
                            container_property_identifier="windTurbines",
                            source=dm.ViewId("my_space", "WindTurbine", "1"),
                        ),
                    },
                    filter=dm.filters.HasData(
                        containers=[dm.ContainerId("my_space", "Asset"), dm.ContainerId("my_space", "WindFarm")]
                    ),
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
        containers=ContainerApplyDict(
            [
                dm.ContainerApply(
                    space="my_space",
                    external_id="Asset",
                    properties={
                        "name": dm.ContainerProperty(type=dm.Text(), nullable=True),
                    },
                ),
                dm.ContainerApply(
                    space="my_space",
                    external_id="WindFarm",
                    properties={
                        "windTurbines": dm.ContainerProperty(
                            type=dm.DirectRelation(is_list=True),
                        ),
                    },
                    constraints={"my_space_Asset": dm.RequiresConstraint(dm.ContainerId("my_space", "Asset"))},
                ),
            ]
        ),
        node_types=NodeApplyDict([]),
    )
    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Property with list of direct relations",
    )

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T08:30:00",
            updated="2024-03-17T08:30:00",
        ),
        properties=[
            DMSInputProperty(
                class_="Asset",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
            DMSInputProperty(
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
            DMSInputView(view="Asset", class_="Asset", in_model=False),
            DMSInputView(view="WindTurbine", class_="WindTurbine", implements="Asset"),
        ],
        containers=[
            DMSInputContainer(container="Asset", class_="Asset"),
            DMSInputContainer(class_="WindTurbine", container="WindTurbine", constraint="Asset"),
        ],
    )
    expected_schema = DMSSchema(
        spaces=SpaceApplyDict([dm.SpaceApply(space="my_space")]),
        data_model=dm.DataModelApply(
            space="my_space",
            external_id="my_data_model",
            version="1",
            description="Creator: Anders",
            views=[
                dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
            ],
        ),
        views=ViewApplyDict(
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
        containers=ContainerApplyDict(
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
        node_types=NodeApplyDict([]),
    )

    yield pytest.param(
        dms_rules,
        expected_schema,
        id="View not in model",
    )

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            # This is a complete schema, but we do not want to trigger the full validation
            schema_="partial",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T11:00:00",
            updated="2024-03-17T11:00:00",
        ),
        properties=[
            DMSInputProperty(
                class_="Asset",
                property_="name",
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
            DMSInputProperty(
                class_="Asset",
                property_="timeseries",
                value_type="CogniteTimeseries",
                connection="reverse(property=asset)",
                is_list=True,
                view="Asset",
                view_property="timeseries",
            ),
            DMSInputProperty(
                class_="Asset",
                property_="root",
                value_type="Asset",
                connection="direct",
                container="Asset",
                container_property="root",
                view="Asset",
                view_property="root",
            ),
            DMSInputProperty(
                class_="Asset",
                property_="children",
                value_type="Asset",
                connection="reverse(property=root)",
                is_list=True,
                view="Asset",
                view_property="children",
            ),
            DMSInputProperty(
                class_="CogniteTimeseries",
                property_="name",
                value_type="text",
                container="CogniteTimeseries",
                container_property="name",
                view="CogniteTimeseries",
                view_property="name",
            ),
            DMSInputProperty(
                class_="CogniteTimeseries",
                property_="asset",
                value_type="Asset",
                connection="direct",
                container="CogniteTimeseries",
                container_property="asset",
                view="CogniteTimeseries",
                view_property="asset",
            ),
            DMSInputProperty(
                class_="CogniteTimeseries",
                property_="activities",
                value_type="Activity",
                connection="direct",
                is_list=True,
                container="CogniteTimeseries",
                container_property="activities",
                view="CogniteTimeseries",
                view_property="activities",
            ),
            DMSInputProperty(
                class_="Activity",
                property_="timeseries",
                value_type="CogniteTimeseries",
                is_list=True,
                connection="reverse(property=activities)",
                view="Activity",
                view_property="timeseries",
            ),
        ],
        views=[
            DMSInputView(view="Asset", class_="Asset"),
            DMSInputView(view="CogniteTimeseries", class_="CogniteTimeseries"),
            DMSInputView(view="Activity", class_="Activity"),
        ],
        containers=[
            DMSInputContainer(container="Asset", class_="Asset"),
            DMSInputContainer(container="CogniteTimeseries", class_="CogniteTimeseries"),
            DMSInputContainer(container="Activity", class_="Activity"),
        ],
    )

    expected_schema = DMSSchema(
        spaces=SpaceApplyDict([dm.SpaceApply(space="my_space")]),
        data_model=dm.DataModelApply(
            space="my_space",
            external_id="my_data_model",
            version="1",
            description="Creator: Anders",
            views=[
                dm.ViewId(space="my_space", external_id="Asset", version="1"),
                dm.ViewId(space="my_space", external_id="CogniteTimeseries", version="1"),
                dm.ViewId(space="my_space", external_id="Activity", version="1"),
            ],
        ),
        views=ViewApplyDict(
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
                            source=dm.ViewId("my_space", "CogniteTimeseries", "1"),
                            through=dm.PropertyId(
                                source=dm.ViewId("my_space", "CogniteTimeseries", "1"), property="asset"
                            ),
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
                    external_id="CogniteTimeseries",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "CogniteTimeseries"),
                            container_property_identifier="name",
                        ),
                        "asset": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "CogniteTimeseries"),
                            container_property_identifier="asset",
                            source=dm.ViewId("my_space", "Asset", "1"),
                        ),
                        "activities": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "CogniteTimeseries"),
                            container_property_identifier="activities",
                            source=dm.ViewId("my_space", "Activity", "1"),
                        ),
                    },
                    filter=dm.filters.HasData(containers=[dm.ContainerId("my_space", "CogniteTimeseries")]),
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="Activity",
                    version="1",
                    properties={
                        "timeseries": dm.MultiReverseDirectRelationApply(
                            source=dm.ViewId("my_space", "CogniteTimeseries", "1"),
                            through=dm.PropertyId(
                                source=dm.ViewId("my_space", "CogniteTimeseries", "1"), property="activities"
                            ),
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
        containers=ContainerApplyDict(
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
                    external_id="CogniteTimeseries",
                    properties={
                        "name": dm.ContainerProperty(type=dm.Text(), nullable=True),
                        "asset": dm.ContainerProperty(type=dm.DirectRelation(), nullable=True),
                        "activities": dm.ContainerProperty(type=dm.DirectRelation(is_list=True), nullable=True),
                    },
                ),
            ]
        ),
        node_types=NodeApplyDict(
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

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T11:00:00",
            updated="2024-03-17T11:00:00",
        ),
        properties=[
            DMSInputProperty(
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
            DMSInputView(view="generating_unit", class_="generating_unit", filter_="NodeType(sp_other:wind_turbine)"),
        ],
        containers=[
            DMSInputContainer(container="generating_unit", class_="generating_unit"),
        ],
    )

    expected_schema = DMSSchema(
        spaces=SpaceApplyDict([dm.SpaceApply(space="my_space")]),
        data_model=dm.DataModelApply(
            space="my_space",
            external_id="my_data_model",
            version="1",
            description="Creator: Anders",
            views=[
                dm.ViewId(space="my_space", external_id="generating_unit", version="1"),
            ],
        ),
        views=ViewApplyDict(
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
        containers=ContainerApplyDict(
            [
                dm.ContainerApply(
                    space="my_space",
                    external_id="generating_unit",
                    properties={"display_name": dm.ContainerProperty(type=dm.Text(), nullable=True)},
                ),
            ]
        ),
        node_types=NodeApplyDict([dm.NodeApply(space="sp_other", external_id="wind_turbine")]),
    )
    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Explict set NodeType Filter",
    )

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            schema_="complete",
            space="sp_solution",
            external_id="solution_model",
            version="1",
            creator="Bob",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSInputProperty(
                class_="Asset",
                property_="kinderen",
                value_type="Asset",
                connection="edge",
                reference="sp_enterprise:Asset(property=children)",
                view="Asset",
                view_property="kinderen",
            ),
        ],
        views=[
            DMSInputView(view="Asset", class_="Asset"),
        ],
    )

    expected_schema = DMSSchema(
        spaces=SpaceApplyDict(
            [
                dm.SpaceApply(space="sp_solution"),
            ]
        ),
        views=ViewApplyDict(
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
        data_model=dm.DataModelApply(
            space="sp_solution",
            external_id="solution_model",
            version="1",
            description="Creator: Bob",
            views=[
                dm.ViewId(space="sp_solution", external_id="Asset", version="1"),
            ],
        ),
        node_types=NodeApplyDict([dm.NodeApply(space="sp_enterprise", external_id="Asset")]),
    )

    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Edge Reference to another data model",
    )


def valid_rules_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="name",
                    value_type="tEXt",
                    container="sp_core:Asset",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="name",
                ),
                DMSInputProperty(
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
                DMSInputContainer(container="sp_core:Asset", class_="Asset"),
                DMSInputContainer(container="GeneratingUnit", constraint="sp_core:Asset", class_="GeneratingUnit"),
            ],
            views=[
                DMSInputView(class_="sp_core:Asset", view="sp_core:Asset"),
                DMSInputView(class_="WindTurbine", view="WindTurbine", implements="sp_core:Asset"),
            ],
        ),
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="name",
                    value_type="text",
                    container="sp_core:Asset",
                    container_property="name",
                    view="sp_core:Asset(version=1)",
                    view_property="name",
                ),
                DMSInputProperty(
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
                DMSInputContainer(container="sp_core:Asset", class_="Asset"),
                DMSInputContainer(class_="GeneratingUnit", container="GeneratingUnit", constraint="sp_core:Asset"),
            ],
            views=[
                DMSInputView(view="sp_core:Asset(version=1)"),
                DMSInputView(class_="WindTurbine", view="WindTurbine", implements="sp_core:Asset(version=1)"),
            ],
        ).as_rules(),
        id="Two properties, two containers, two views. Primary data types, no relations.",
    )

    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="Plant",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    class_="Plant",
                    property_="generators",
                    connection="edge",
                    value_type="Generator",
                    view="Plant",
                    view_property="generators",
                ),
                DMSInputProperty(
                    class_="Plant",
                    property_="reservoir",
                    connection="direct",
                    value_type="Reservoir",
                    container="Asset",
                    container_property="child",
                    view="Plant",
                    view_property="reservoir",
                ),
                DMSInputProperty(
                    class_="Generator",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
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
                DMSInputContainer(class_="Asset", container="Asset"),
                DMSInputContainer(
                    class_="Plant",
                    container="Plant",
                    constraint="Asset",
                ),
            ],
            views=[
                DMSInputView(class_="Asset", view="Asset"),
                DMSInputView(class_="Plant", view="Plant", implements="Asset"),
                DMSInputView(class_="Generator", view="Generator", implements="Asset"),
                DMSInputView(class_="Reservoir", view="Reservoir", implements="Asset"),
            ],
        ),
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="Plant",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    class_="Plant",
                    property_="generators",
                    value_type="Generator",
                    connection="edge",
                    view="Plant",
                    view_property="generators",
                ),
                DMSInputProperty(
                    class_="Plant",
                    property_="reservoir",
                    value_type="Reservoir",
                    connection="direct",
                    container="Asset",
                    container_property="child",
                    view="Plant",
                    view_property="reservoir",
                ),
                DMSInputProperty(
                    class_="Generator",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
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
                DMSInputContainer(container="Asset", class_="Asset"),
                DMSInputContainer(class_="Plant", container="Plant", constraint="Asset"),
            ],
            views=[
                DMSInputView(view="Asset", class_="Asset"),
                DMSInputView(class_="Plant", view="Plant", implements="Asset"),
                DMSInputView(class_="Generator", view="Generator", implements="Asset"),
                DMSInputView(class_="Reservoir", view="Reservoir", implements="Asset"),
            ],
        ).as_rules(),
        id="Five properties, two containers, four views. Direct relations and Multiedge.",
    )


def invalid_container_definitions_test_cases() -> Iterable[ParameterSet]:
    container_id = dm.ContainerId("my_space", "GeneratingUnit")
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="maxPower",
                    value_type="float64",
                    is_list=False,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
                DMSInputProperty(
                    class_="HydroGenerator",
                    property_="maxPower",
                    value_type="float32",
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
            ],
            views=[
                DMSInputView(view="WindTurbine"),
                DMSInputView(view="sp_core:Asset"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id, "container", "maxPower", frozenset({"float64", "float32"}), (0, 1), "rows"
            )
        ],
        id="Inconsistent container definition value type",
    )

    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="maxPower",
                    value_type="float64",
                    is_list=True,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
                DMSInputProperty(
                    class_="HydroGenerator",
                    property_="maxPower",
                    value_type="float64",
                    is_list=False,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
            ],
            views=[
                DMSInputView(view="WindTurbine"),
                DMSInputView(view="sp_core:Asset"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id, "container", "maxPower", frozenset({True, False}), (0, 1), "rows"
            )
        ],
        id="Inconsistent container definition isList",
    )
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="maxPower",
                    value_type="float64",
                    nullable=True,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
                DMSInputProperty(
                    class_="HydroGenerator",
                    property_="maxPower",
                    value_type="float64",
                    nullable=False,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
            ],
            views=[
                DMSInputView(view="WindTurbine"),
                DMSInputView(view="sp_core:Asset"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id, "container", "maxPower", frozenset({True, False}), (0, 1), "rows"
            )
        ],
        id="Inconsistent container definition nullable",
    )
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="name",
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    index="name",
                ),
                DMSInputProperty(
                    class_="HydroGenerator",
                    property_="name",
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    index="name_index",
                ),
            ],
            views=[
                DMSInputView(view="WindTurbine"),
                DMSInputView(view="sp_core:Asset"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id, "container", "name", frozenset({"name", "name_index"}), (0, 1), "rows"
            )
        ],
        id="Inconsistent container definition index",
    )
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindTurbine",
                    property_="name",
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    constraint="unique_name",
                ),
                DMSInputProperty(
                    class_="HydroGenerator",
                    property_="name",
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    constraint="name",
                ),
            ],
            views=[
                DMSInputView(view="WindTurbine"),
                DMSInputView(view="sp_core:Asset"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id, "container", "name", frozenset({"unique_name", "name"}), (0, 1), "rows"
            )
        ],
        id="Inconsistent container definition constraint",
    )


def invalid_extended_rules_test_cases() -> Iterable[ParameterSet]:
    last_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            schema_="complete",
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSInputProperty(
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
            DMSInputContainer(container="Asset", class_="Asset"),
        ],
        views=[
            DMSInputView(view="Asset", class_="Asset"),
        ],
    )

    changing_container = DMSInputRules(
        metadata=DMSInputMetadata(
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
            DMSInputProperty(
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
            DMSInputContainer(container="Asset", class_="Asset"),
        ],
        views=[
            DMSInputView(view="Asset", class_="Asset"),
        ],
        last=last_rules,
    )

    yield pytest.param(
        changing_container,
        [
            ResourceChangedError(
                dm.ContainerId("my_space", "Asset"),
                "container",
                frozenset({"name"}),
                frozenset({}),
            )
        ],
        id="Addition extension, changing container",
    )

    changing_view = DMSInputRules(
        metadata=DMSInputMetadata(
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
            DMSInputProperty(
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
            DMSInputContainer(container="Asset", class_="Asset"),
        ],
        views=[
            DMSInputView(view="Asset", class_="Asset", description="Change not allowed"),
        ],
        last=last_rules,
    )

    yield pytest.param(
        changing_view,
        [
            ResourceChangedError(
                dm.ViewId("my_space", "Asset", "1"),
                "view",
                frozenset({}),
                frozenset({"description"}),
            )
        ],
        id="Addition extension, changing view",
    )

    changing_container2 = dataclasses.replace(changing_container)
    changing_container2.metadata.extension = "reshape"

    yield pytest.param(
        changing_container2,
        [
            ResourceChangedError(
                dm.ContainerId("my_space", "Asset"),
                "container",
                frozenset({"name"}),
                frozenset({}),
            )
        ],
    )


def case_unknown_value_types():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "prefix": "power",
                "created": datetime.datetime(2024, 2, 9, 0, 0),
                "updated": datetime.datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
            },
            "Classes": [
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                }
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "StrING",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                },
                {
                    "Class": "GeneratingUnit",
                    "Property": "voltage",
                    "Description": None,
                    "Value Type": UnknownEntity(),
                    "Min Count": None,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                },
            ],
        },
        1,
        id="case_unknown_value_type",
    )


class TestDMSRules:
    def test_load_valid_alice_rules(self, alice_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DMSInputRules.load(alice_spreadsheet).as_rules()

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

    @pytest.mark.parametrize("raw, no_properties", list(case_unknown_value_types()))
    def test_case_unknown_value_types(self, raw: dict[str, dict[str, Any]], no_properties: int) -> None:
        rules = InformationRules.model_validate(raw)
        dms_rules = InformationToDMS(ignore_undefined_value_types=True).transform(rules).rules
        assert len(dms_rules.properties) == no_properties

    @pytest.mark.parametrize("raw, expected_rules", list(valid_rules_tests_cases()))
    def test_load_valid_rules(self, raw: DMSInputRules, expected_rules: DMSRules) -> None:
        valid_rules = raw.as_rules()
        assert valid_rules.model_dump() == expected_rules.model_dump()
        # testing case insensitive value types
        assert isinstance(valid_rules.properties[0].value_type, String)

    @pytest.mark.parametrize("raw, expected_errors", list(invalid_container_definitions_test_cases()))
    def test_load_inconsistent_container_definitions(
        self, raw: DMSInputRules, expected_errors: list[NeatError]
    ) -> None:
        with pytest.raises(ValueError) as e:
            raw.as_rules()

        assert isinstance(e.value, ValidationError)
        validation_errors = e.value.errors()
        assert len(validation_errors) == 1, "Expected there to be exactly one validation error"
        validation_error = validation_errors[0]
        multi_value_error = validation_error.get("ctx", {}).get("error")
        assert isinstance(multi_value_error, MultiValueError)
        actual_errors = multi_value_error.errors

        assert sorted(actual_errors) == sorted(expected_errors)

    def test_alice_to_and_from_DMS(self, alice_rules: DMSRules) -> None:
        schema = alice_rules.as_schema()
        recreated_rules = ImporterPipeline.verify(DMSImporter(schema))

        exclude = {
            # This information is lost in the conversion
            "metadata": {"created", "updated"},
            "properties": {"data": {"__all__": {"reference"}}},
            # The Exporter adds node types for each view as this is an Enterprise model.
            "nodes": "__all__",
        }
        assert recreated_rules.dump(exclude=exclude) == alice_rules.dump(exclude=exclude)

    @pytest.mark.parametrize("input_rules, expected_schema", rules_schema_tests_cases())
    def test_as_schema(self, input_rules: DMSInputRules, expected_schema: DMSSchema) -> None:
        rules = input_rules.as_rules()
        actual_schema = rules.as_schema()

        assert actual_schema.spaces.dump() == expected_schema.spaces.dump()
        actual_schema.data_model.views = sorted(actual_schema.data_model.views, key=lambda v: v.external_id)
        expected_schema.data_model.views = sorted(expected_schema.data_model.views, key=lambda v: v.external_id)
        assert actual_schema.data_model.dump() == expected_schema.data_model.dump()
        assert actual_schema.containers.dump() == expected_schema.containers.dump()

        actual_schema.views = ViewApplyDict(sorted(actual_schema.views.values(), key=lambda v: v.external_id))
        expected_schema.views = ViewApplyDict(sorted(expected_schema.views.values(), key=lambda v: v.external_id))
        assert actual_schema.views.dump() == expected_schema.views.dump()

        actual_schema.node_types = NodeApplyDict(sorted(actual_schema.node_types.values(), key=lambda n: n.external_id))
        expected_schema.node_types = NodeApplyDict(
            sorted(expected_schema.node_types.values(), key=lambda n: n.external_id)
        )
        assert actual_schema.node_types.dump() == expected_schema.node_types.dump()

    def test_alice_as_information(self, alice_spreadsheet: dict[str, dict[str, Any]]) -> None:
        alice_rules = DMSInputRules.load(alice_spreadsheet).as_rules()
        info_rules = DMSToInformation().transform(alice_rules).rules

        assert isinstance(info_rules, InformationRules)

    def test_dump_skip_default_space_and_version(self) -> None:
        dms_rules = DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="partial",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2024-03-16",
                updated="2024-03-16",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindFarm",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="WindFarm",
                    view_property="name",
                ),
            ],
            views=[DMSInputView(view="WindFarm", class_="WindFarm", implements="Sourceable,Describable")],
            containers=[DMSInputContainer(container="Asset", class_="Asset", constraint="Sourceable,Describable")],
        ).as_rules()
        expected_dump = {
            "metadata": {
                "role": "DMS Architect",
                "schema_": "partial",
                "data_model_type": "solution",
                "extension": "addition",
                "space": "my_space",
                "external_id": "my_data_model",
                "creator": "Anders",
                "created": datetime.datetime(2024, 3, 16),
                "updated": datetime.datetime(2024, 3, 16),
                "version": "1",
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

        actual_dump = dms_rules.dump(exclude_none=True, exclude_unset=True, exclude_defaults=True)

        assert actual_dump == expected_dump

    def test_olav_as_information(self, olav_dms_rules: DMSRules) -> None:
        info_rules_copy = olav_dms_rules.model_copy(deep=True)
        # In Olav's Rules, the references are set for traceability. We remove it
        # to test that the references are correctly set in the conversion.
        for prop in info_rules_copy.properties:
            prop.reference = None
        for view in info_rules_copy.views:
            view.reference = None

        info_rules = DMSToInformation().transform(olav_dms_rules).rules

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
    def test_load_invalid_extended_rules(self, rules: DMSInputRules, expected_issues: list[NeatIssue]):
        raw = rules.dump()
        raw["Metadata"]["schema"] = "extended"

        with pytest.raises(ValidationError) as e:
            DMSInputRules.load(raw).as_rules()

        actual_issues = NeatError.from_pydantic_errors(e.value.errors())

        assert sorted(actual_issues) == sorted(expected_issues)

    def test_create_reference(self) -> None:
        pipeline = RulesPipeline[InformationRules, DMSRules](
            [
                InformationToDMS(),
                MapOneToOne(car.BASE_MODEL, {"Manufacturer": "Entity", "Color": "Entity"}),
            ]
        )
        dms_rules = pipeline.run(car.CAR_RULES)

        schema = dms_rules.as_schema()
        view_by_external_id = {view.external_id: view for view in schema.views.values()}
        # The Manufacturer and Color view only has one property, name, and this is
        # now expected to point to the Entity container in the base model.
        manufacturer_view = view_by_external_id["Manufacturer"]
        assert manufacturer_view.referenced_containers() == {dm.ContainerId(car.BASE_MODEL.metadata.space, "Entity")}
        color_view = view_by_external_id["Color"]
        assert color_view.referenced_containers() == {dm.ContainerId(car.BASE_MODEL.metadata.space, "Entity")}


class TestDMSExporter:
    def test_default_filters_using_olav_dms_rules(self, olav_dms_rules: DMSRules) -> None:
        set_filter = {view.view.as_id() for view in olav_dms_rules.views if view.filter_ is not None}
        assert not set_filter, f"Expected no filters to be set, but got {set_filter}"

        schema = olav_dms_rules.as_schema()
        view_by_external_id = {view.external_id: view for view in schema.views.values()}

        wind_turbine = view_by_external_id.get("WindTurbine")
        assert wind_turbine is not None
        assert (
            wind_turbine.filter.dump()
            == dm.filters.In(
                ["node", "type"],
                [{"space": "power", "externalId": "GeneratingUnit"}, {"space": "power", "externalId": "WindTurbine"}],
            ).dump()
        )

        wind_farm = view_by_external_id.get("WindFarm")
        assert wind_farm is not None
        assert (
            wind_farm.filter.dump()
            == dm.filters.In(
                ["node", "type"],
                [{"space": "power", "externalId": "EnergyArea"}, {"space": "power", "externalId": "WindFarm"}],
            ).dump()
        )

        weather_station = view_by_external_id.get("WeatherStation")
        assert weather_station is not None
        assert (
            weather_station.filter.dump()
            == dm.filters.HasData(containers=[dm.ContainerId("power_analytics", "WeatherStation")]).dump()
        )

        power_forecast = view_by_external_id.get("PowerForecast")
        assert power_forecast is not None
        assert (
            power_forecast.filter.dump()
            == dm.filters.HasData(containers=[dm.ContainerId("power_analytics", "PowerForecast")]).dump()
        )

        point = view_by_external_id.get("Point")
        assert point is not None
        assert point.filter.dump() == dm.filters.HasData(containers=[dm.ContainerId("power", "Point")]).dump()

        # Polygon has a NodeType filter in the enterprise model (no container properties)
        polygon = view_by_external_id.get("Polygon")
        assert polygon is not None
        assert (
            polygon.filter.dump()
            == dm.filters.Equals(["node", "type"], {"space": "power", "externalId": "Polygon"}).dump()
        )

    def test_svein_harald_as_schema(self, svein_harald_dms_rules: DMSRules) -> None:
        expected_views = {"GeneratingUnit", "EnergyArea", "TimeseriesForecastProduct"}
        expected_model_views = expected_views | {
            "ArrayCable",
            "CircuitBreaker",
            "CurrentTransformer",
            "DisconnectSwitch",
            "DistributionLine",
            "DistributionSubstation",
            "ElectricCarCharger",
            "EnergyArea",
            "EnergyConsumer",
            "ExportCable",
            "GeneratingUnit",
            "GeoLocation",
            "Meter",
            "MultiLineString",
            "OffshoreSubstation",
            "OnshoreSubstation",
            "Point",
            "Polygon",
            "PowerLine",
            "Substation",
            "Transmission",
            "TransmissionSubstation",
            "VoltageLevel",
            "VoltageTransformer",
            "WindFarm",
            "WindTurbine",
        }

        schema = svein_harald_dms_rules.as_schema()

        actual_views = {view.external_id for view in schema.views}
        assert actual_views == expected_views
        actual_model_views = {view.external_id for view in schema.data_model.views}
        assert actual_model_views == expected_model_views

    def test_olav_rebuild_as_schema(self, olav_rebuild_dms_rules: DMSRules) -> None:
        expected_views = {
            "Point",
            "Polygon",
            "PowerForecast",
            "WeatherStation",
            "WindFarm",
            "WindTurbine",
            "TimeseriesForecastProduct",
        }
        expected_containers = {"PowerForecast", "WeatherStation"}

        schema = olav_rebuild_dms_rules.as_schema()

        actual_views = {view.external_id for view in schema.views}
        assert actual_views == expected_views
        actual_model_views = {view.external_id for view in schema.data_model.views}
        assert actual_model_views == expected_views
        actual_containers = {container.external_id for container in schema.containers}
        assert actual_containers == expected_containers
        missing_properties = {
            view_id for view_id, view in schema.views.items() if not view.properties and not view.implements
        }
        assert not missing_properties, f"Missing properties for views: {missing_properties}"

    def test_camilla_business_solution_as_schema(self, camilla_information_rules: InformationRules) -> None:
        dms_rules = InformationToDMS().transform(camilla_information_rules).rules
        expected_views = {"TimeseriesForecastProduct", "WindFarm"}

        schema = dms_rules.as_schema()

        assert {v.external_id for v in schema.views} == expected_views
        assert {v.external_id for v in schema.data_model.views} == expected_views
        product = next((v for v in schema.views.values() if v.external_id == "TimeseriesForecastProduct"), None)
        assert product is not None
        assert not product.properties, f"Expected no properties for {product.external_id}"
        assert product.implements == [dm.ViewId("power", "TimeseriesForecastProduct", "0.1.0")]

        wind_farm = next((v for v in schema.views.values() if v.external_id == "WindFarm"), None)
        assert wind_farm is not None
        assert set(wind_farm.properties) == {"name", "powerForecast"}
        assert wind_farm.referenced_containers() == {dm.ContainerId("power", "EnergyArea")}


def test_dms_rules_validation_error():
    with pytest.raises(NeatError) as e:
        dms_rules = DMSInputRules(
            metadata=DMSInputMetadata(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2024-03-16",
                updated="2024-03-16",
            ),
            properties=[
                DMSInputProperty(
                    class_="WindFarm",
                    property_="name",
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="WindFarm",
                    view_property="name",
                ),
            ],
            views=[DMSInputView(view="WindFarm", class_="WindFarm", implements="Sourceable,Describable")],
            containers=[DMSInputContainer(container="Asset", class_="Asset", constraint="Sourceable,Describable")],
        )

        dms_rules.as_rules()

    assert e.value == ResourceNotFoundError(
        dm.ViewId(space="my_space", external_id="Sourceable", version="1"),
        "view",
        dm.ViewId(space="my_space", external_id="WindFarm", version="1"),
        "view",
    )
