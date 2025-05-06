import datetime
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm
from pydantic import ValidationError

from cognite.neat.core._client.data_classes.data_modeling import (
    ContainerApplyDict,
    NodeApplyDict,
    SpaceApplyDict,
    ViewApplyDict,
)
from cognite.neat.core._issues import NeatError, catch_issues
from cognite.neat.core._issues.errors import PropertyDefinitionDuplicatedError
from cognite.neat.core._issues.errors._resources import ResourceDuplicatedError
from cognite.neat.core._issues.warnings.user_modeling import (
    ViewsAndDataModelNotInSameSpaceWarning,
)
from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.importers import DMSImporter
from cognite.neat.core._rules.models import DMSRules, InformationRules
from cognite.neat.core._rules.models.data_types import String
from cognite.neat.core._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputNode,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
    DMSMetadata,
    DMSProperty,
    DMSSchema,
    DMSValidation,
)
from cognite.neat.core._rules.models.dms._exporter import _DMSExporter
from cognite.neat.core._rules.models.entities._single_value import (
    ContainerEntity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat.core._rules.transformers import (
    DMSToInformation,
    InformationToDMS,
    MapOneToOne,
    VerifyDMSRules,
)
from tests.data import GraphData
from tests.utils import normalize_neat_id_in_rules


def rules_schema_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
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
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    value_type="float64",
                    container="GeneratingUnit",
                    container_property="ratedPower",
                    view="WindTurbine",
                    view_property="ratedPower",
                ),
                DMSInputProperty(
                    value_type="WindTurbine",
                    connection="edge",
                    view="WindFarm",
                    view_property="windTurbines",
                ),
            ],
            containers=[
                DMSInputContainer(
                    container="Asset",
                ),
                DMSInputContainer(container="GeneratingUnit", constraint="Asset"),
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
                                container=dm.ContainerId("my_space", "Asset"),
                                container_property_identifier="name",
                            )
                        },
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
                    ),
                    dm.ViewApply(
                        space="my_space",
                        external_id="WindFarm",
                        version="1",
                        properties={
                            "windTurbines": dm.MultiEdgeConnectionApply(
                                type=dm.DirectRelationReference(
                                    space="my_space",
                                    external_id="WindFarm.windTurbines",
                                ),
                                source=dm.ViewId(
                                    space="my_space",
                                    external_id="WindTurbine",
                                    version="1",
                                ),
                                direction="outwards",
                            )
                        },
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
            node_types=NodeApplyDict([]),
        ),
        id="Two properties, one container, one view",
    )

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-16T23:00:00",
            updated="2024-03-16T23:00:00",
        ),
        properties=[
            DMSInputProperty(
                value_type="text",
                container="Asset",
                container_property="name",
                view="WindFarm",
                view_property="name",
            ),
            DMSInputProperty(
                value_type="WindTurbine",
                connection="direct",
                max_count=100,
                container="WindFarm",
                container_property="windTurbines",
                view="WindFarm",
                view_property="windTurbines",
            ),
            DMSInputProperty(
                value_type="text",
                container="Asset",
                container_property="name",
                view="WindTurbine",
                view_property="name",
            ),
        ],
        views=[
            DMSInputView(view="WindFarm"),
            DMSInputView(view="WindTurbine"),
        ],
        containers=[
            DMSInputContainer(container="Asset"),
            DMSInputContainer(container="WindFarm", constraint="Asset"),
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
                            container=dm.ContainerId("my_space", "Asset"),
                            container_property_identifier="name",
                        ),
                        "windTurbines": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "WindFarm"),
                            container_property_identifier="windTurbines",
                            source=dm.ViewId("my_space", "WindTurbine", "1"),
                        ),
                    },
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="WindTurbine",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"),
                            container_property_identifier="name",
                        )
                    },
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
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T08:30:00",
            updated="2024-03-17T08:30:00",
        ),
        properties=[
            DMSInputProperty(
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
            DMSInputProperty(
                value_type="float64",
                container="WindTurbine",
                container_property="maxPower",
                view="WindTurbine",
                view_property="maxPower",
            ),
        ],
        views=[
            DMSInputView(view="Asset", in_model=False),
            DMSInputView(view="WindTurbine", implements="Asset"),
        ],
        containers=[
            DMSInputContainer(container="Asset"),
            DMSInputContainer(container="WindTurbine", constraint="Asset"),
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
                            container=dm.ContainerId("my_space", "Asset"),
                            container_property_identifier="name",
                        ),
                    },
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
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T11:00:00",
            updated="2024-03-17T11:00:00",
        ),
        properties=[
            DMSInputProperty(
                value_type="text",
                container="Asset",
                container_property="name",
                view="Asset",
                view_property="name",
            ),
            DMSInputProperty(
                value_type="CogniteTimeseries",
                connection="reverse(property=asset)",
                max_count=float("inf"),
                view="Asset",
                view_property="timeseries",
            ),
            DMSInputProperty(
                value_type="Asset",
                connection="direct",
                container="Asset",
                container_property="root",
                view="Asset",
                view_property="root",
                max_count=1,
            ),
            DMSInputProperty(
                value_type="Asset",
                connection="reverse(property=root)",
                max_count=float("inf"),
                view="Asset",
                view_property="children",
            ),
            DMSInputProperty(
                value_type="text",
                container="CogniteTimeseries",
                container_property="name",
                view="CogniteTimeseries",
                view_property="name",
                max_count=1,
            ),
            DMSInputProperty(
                value_type="Asset",
                connection="direct",
                container="CogniteTimeseries",
                container_property="asset",
                view="CogniteTimeseries",
                view_property="asset",
                max_count=1,
            ),
            DMSInputProperty(
                value_type="Activity",
                connection="direct",
                max_count=100,
                container="CogniteTimeseries",
                container_property="activities",
                view="CogniteTimeseries",
                view_property="activities",
            ),
            DMSInputProperty(
                value_type="CogniteTimeseries",
                max_count=float("inf"),
                connection="reverse(property=activities)",
                view="Activity",
                view_property="timeseries",
            ),
        ],
        views=[
            DMSInputView(
                view="Asset",
            ),
            DMSInputView(view="CogniteTimeseries"),
            DMSInputView(view="Activity"),
        ],
        containers=[
            DMSInputContainer(container="Asset"),
            DMSInputContainer(container="CogniteTimeseries"),
            DMSInputContainer(container="Activity"),
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
                            container=dm.ContainerId("my_space", "Asset"),
                            container_property_identifier="name",
                        ),
                        "timeseries": dm.MultiReverseDirectRelationApply(
                            source=dm.ViewId("my_space", "CogniteTimeseries", "1"),
                            through=dm.PropertyId(
                                source=dm.ViewId("my_space", "CogniteTimeseries", "1"),
                                property="asset",
                            ),
                        ),
                        "root": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "Asset"),
                            container_property_identifier="root",
                            source=dm.ViewId("my_space", "Asset", "1"),
                        ),
                        "children": dm.MultiReverseDirectRelationApply(
                            source=dm.ViewId("my_space", "Asset", "1"),
                            through=dm.PropertyId(
                                source=dm.ViewId("my_space", "Asset", "1"),
                                property="root",
                            ),
                        ),
                    },
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
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="Activity",
                    version="1",
                    properties={
                        "timeseries": dm.MultiReverseDirectRelationApply(
                            source=dm.ViewId("my_space", "CogniteTimeseries", "1"),
                            through=dm.PropertyId(
                                source=dm.ViewId("my_space", "CogniteTimeseries", "1"),
                                property="activities",
                            ),
                        )
                    },
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
        node_types=NodeApplyDict([]),
    )
    yield pytest.param(
        dms_rules,
        expected_schema,
        id="Multiple relations and reverse relations",
    )

    dms_rules = DMSInputRules(
        metadata=DMSInputMetadata(
            space="my_space",
            external_id="my_data_model",
            version="1",
            creator="Anders",
            created="2024-03-17T11:00:00",
            updated="2024-03-17T11:00:00",
        ),
        properties=[
            DMSInputProperty(
                value_type="text",
                container="generating_unit",
                container_property="display_name",
                view="generating_unit",
                view_property="display_name",
            )
        ],
        views=[
            DMSInputView(view="generating_unit", filter_="NodeType(sp_other:wind_turbine)"),
        ],
        containers=[
            DMSInputContainer(container="generating_unit"),
        ],
        nodes=[DMSInputNode(node="sp_other:wind_turbine", usage="type")],
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
                    filter=dm.filters.Equals(["node", "type"], {"space": "sp_other", "externalId": "wind_turbine"}),
                    properties={
                        "display_name": dm.MappedPropertyApply(
                            container=dm.ContainerId("my_space", "generating_unit"),
                            container_property_identifier="display_name",
                        ),
                    },
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
            space="sp_solution",
            external_id="solution_model",
            version="1",
            creator="Bob",
            created="2021-01-01T00:00:00",
            updated="2021-01-01T00:00:00",
        ),
        properties=[
            DMSInputProperty(
                value_type="Asset",
                connection="edge(type=sp_enterprise:Asset)",
                view="Asset",
                view_property="kinderen",
            ),
        ],
        views=[
            DMSInputView(view="Asset"),
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
                                external_id="Asset",
                            ),
                            source=dm.ViewId("sp_solution", "Asset", "1"),
                            direction="outwards",
                        ),
                    },
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
        node_types=NodeApplyDict([]),
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
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="tEXt",
                    container="sp_core:Asset",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    value_type="float64",
                    container="GeneratingUnit",
                    container_property="ratedPower",
                    view="WindTurbine",
                    view_property="ratedPower",
                ),
            ],
            containers=[
                DMSInputContainer(
                    container="sp_core:Asset",
                ),
                DMSInputContainer(
                    container="GeneratingUnit",
                    constraint="sp_core:Asset",
                ),
            ],
            views=[
                DMSInputView(view="sp_core:Asset"),
                DMSInputView(view="WindTurbine", implements="sp_core:Asset"),
            ],
        ),
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="text",
                    container="sp_core:Asset",
                    container_property="name",
                    view="sp_core:Asset(version=1)",
                    view_property="name",
                ),
                DMSInputProperty(
                    value_type="float64",
                    container="GeneratingUnit",
                    container_property="ratedPower",
                    view="WindTurbine",
                    view_property="ratedPower",
                ),
            ],
            containers=[
                DMSInputContainer(
                    container="sp_core:Asset",
                ),
                DMSInputContainer(container="GeneratingUnit", constraint="sp_core:Asset"),
            ],
            views=[
                DMSInputView(view="sp_core:Asset(version=1)"),
                DMSInputView(view="WindTurbine", implements="sp_core:Asset(version=1)"),
            ],
        ).as_verified_rules(),
        id="Two properties, two containers, two views. Primary data types, no relations.",
    )

    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    connection="edge",
                    value_type="Generator",
                    view="Plant",
                    view_property="generators",
                ),
                DMSInputProperty(
                    connection="direct",
                    value_type="Reservoir",
                    container="Asset",
                    container_property="child",
                    view="Plant",
                    view_property="reservoir",
                ),
            ],
            containers=[
                DMSInputContainer(container="Asset"),
                DMSInputContainer(
                    container="Plant",
                    constraint="Asset",
                ),
            ],
            views=[
                DMSInputView(view="Asset"),
                DMSInputView(view="Plant", implements="Asset"),
                DMSInputView(view="Generator", implements="Asset"),
                DMSInputView(view="Reservoir", implements="Asset"),
            ],
        ),
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="Asset",
                    view_property="name",
                ),
                DMSInputProperty(
                    value_type="Generator",
                    connection="edge",
                    view="Plant",
                    view_property="generators",
                ),
                DMSInputProperty(
                    value_type="Reservoir",
                    connection="direct",
                    container="Asset",
                    container_property="child",
                    view="Plant",
                    view_property="reservoir",
                ),
            ],
            containers=[
                DMSInputContainer(container="Asset"),
                DMSInputContainer(container="Plant", constraint="Asset"),
            ],
            views=[
                DMSInputView(view="Asset"),
                DMSInputView(view="Plant", implements="Asset"),
                DMSInputView(view="Generator", implements="Asset"),
                DMSInputView(view="Reservoir", implements="Asset"),
            ],
        ).as_verified_rules(),
        id="Five properties, two containers, four views. Direct relations and Multiedge.",
    )


def invalid_container_definitions_test_cases() -> Iterable[ParameterSet]:
    container_id = dm.ContainerId("my_space", "GeneratingUnit")
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="float64",
                    max_count=1,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
                DMSInputProperty(
                    value_type="float32",
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
            ],
            views=[
                DMSInputView(view="sp_core:Asset"),
            ],
            containers=[
                DMSInputContainer(container="GeneratingUnit"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id,
                "container",
                "maxPower",
                frozenset({"float64", "float32"}),
                (0, 1),
                "rows",
            ),
            ResourceDuplicatedError(
                identifier="maxPower",
                resource_type="property",
                location="the Properties sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
            ViewsAndDataModelNotInSameSpaceWarning(
                data_model_space="my_space",
                views_spaces="sp_core",
            ),
        ],
        id="Inconsistent container definition value type",
    )

    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="float64",
                    max_count=1000,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
                DMSInputProperty(
                    value_type="float64",
                    max_count=1,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
            ],
            views=[
                DMSInputView(view="sp_core:Asset"),
            ],
            containers=[
                DMSInputContainer(container="GeneratingUnit"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id,
                "container",
                "maxPower",
                frozenset({True, False}),
                (0, 1),
                "rows",
            ),
            ResourceDuplicatedError(
                identifier="maxPower",
                resource_type="property",
                location="the Properties sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
            ViewsAndDataModelNotInSameSpaceWarning(
                data_model_space="my_space",
                views_spaces="sp_core",
            ),
        ],
        id="Inconsistent container definition isList",
    )
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="float64",
                    min_count=0,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
                DMSInputProperty(
                    value_type="float64",
                    min_count=1,
                    container="GeneratingUnit",
                    container_property="maxPower",
                    view="sp_core:Asset",
                    view_property="maxPower",
                ),
            ],
            views=[
                DMSInputView(view="sp_core:Asset"),
            ],
            containers=[
                DMSInputContainer(container="GeneratingUnit"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id,
                "container",
                "maxPower",
                frozenset({True, False}),
                (0, 1),
                "rows",
            ),
            ResourceDuplicatedError(
                identifier="maxPower",
                resource_type="property",
                location="the Properties sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
            ViewsAndDataModelNotInSameSpaceWarning(
                data_model_space="my_space",
                views_spaces="sp_core",
            ),
        ],
        id="Inconsistent container definition nullable",
    )
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    index="name",
                ),
                DMSInputProperty(
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    index="name_index",
                ),
            ],
            views=[
                DMSInputView(view="sp_core:Asset"),
            ],
            containers=[
                DMSInputContainer(container="GeneratingUnit"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id,
                "container",
                "name",
                frozenset({"name", "name_index"}),
                (0, 1),
                "rows",
            ),
            ResourceDuplicatedError(
                identifier="maxPower",
                resource_type="property",
                location="the Properties sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
            ViewsAndDataModelNotInSameSpaceWarning(
                data_model_space="my_space",
                views_spaces="sp_core",
            ),
        ],
        id="Inconsistent container definition index",
    )
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=[
                DMSInputProperty(
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    constraint="unique_name",
                ),
                DMSInputProperty(
                    value_type="text",
                    container="GeneratingUnit",
                    container_property="name",
                    view="sp_core:Asset",
                    view_property="maxPower",
                    constraint="name",
                ),
            ],
            views=[
                DMSInputView(view="sp_core:Asset"),
            ],
            containers=[
                DMSInputContainer(container="GeneratingUnit"),
            ],
        ),
        [
            PropertyDefinitionDuplicatedError(
                container_id,
                "container",
                "name",
                frozenset({"unique_name", "name"}),
                (0, 1),
                "rows",
            ),
            ResourceDuplicatedError(
                identifier="maxPower",
                resource_type="property",
                location="the Properties sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
            ViewsAndDataModelNotInSameSpaceWarning(
                data_model_space="my_space",
                views_spaces="sp_core",
            ),
        ],
        id="Inconsistent container definition constraint",
    )


def case_unknown_value_types():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "space": "power",
                "external_id": "power2consumer",
                "created": datetime.datetime(2024, 2, 9, 0, 0),
                "updated": datetime.datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "name": "Power to Consumer Data Model",
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
        valid_rules = DMSInputRules.load(alice_spreadsheet).as_verified_rules()

        assert isinstance(valid_rules, DMSRules)

        sample_expected_properties = {
            "power:GeneratingUnit(version=0.1.0).name",
            "power:WindFarm(version=0.1.0).windTurbines",
            "power:Substation(version=0.1.0).mainTransformer",
        }
        missing = sample_expected_properties - {
            f"{prop.view.versioned_id}.{prop.view_property}" for prop in valid_rules.properties
        }
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("raw, no_properties", list(case_unknown_value_types()))
    def test_case_unknown_value_types(self, raw: dict[str, dict[str, Any]], no_properties: int) -> None:
        rules = InformationRules.model_validate(raw)
        dms_rules = InformationToDMS(ignore_undefined_value_types=True).transform(rules)
        assert len(dms_rules.properties) == no_properties

    @pytest.mark.parametrize("raw, expected_rules", list(valid_rules_tests_cases()))
    def test_load_valid_rules(self, raw: DMSInputRules, expected_rules: DMSRules) -> None:
        valid_rules = raw.as_verified_rules()
        normalize_neat_id_in_rules(valid_rules)
        normalize_neat_id_in_rules(expected_rules)

        assert valid_rules.model_dump() == expected_rules.model_dump()
        issues = DMSValidation(valid_rules).validate()
        assert not issues
        # testing case insensitive value types
        assert isinstance(valid_rules.properties[0].value_type, String)

    @pytest.mark.parametrize("raw, expected_errors", list(invalid_container_definitions_test_cases()))
    def test_load_inconsistent_container_definitions(
        self, raw: DMSInputRules, expected_errors: list[NeatError]
    ) -> None:
        rules = raw.as_verified_rules()
        issues = DMSValidation(rules).validate()

        assert len(issues.errors) == 2

        assert sorted(issues) == sorted(expected_errors)

    def test_alice_to_and_from_dms(self, alice_rules: DMSRules) -> None:
        schema = alice_rules.as_schema()
        recreated_rules = DMSImporter(schema).to_rules().rules.as_verified_rules()

        exclude = {
            # This information is lost in the conversion
            "metadata": {"created", "updated"},
            "properties": {"__all__": {"reference", "neatId"}},
            "views": {"__all__": {"neatId"}},
            "containers": {"__all__": {"neatId"}},
            # The Exporter adds node types for each view as this is an Enterprise model.
            "nodes": {"__all__"},
        }
        args = {"exclude_none": True, "sort": True, "exclude_unset": True, "exclude_defaults": True, "exclude": exclude}
        dumped = recreated_rules.dump(**args)
        # The exclude above leaves an empty list for nodes, so we set it to None, to match the input.
        if not dumped.get("nodes"):
            dumped.pop("nodes", None)
        assert dumped == alice_rules.dump(**args)

    @pytest.mark.parametrize("input_rules, expected_schema", rules_schema_tests_cases())
    def test_as_schema(self, input_rules: DMSInputRules, expected_schema: DMSSchema) -> None:
        rules = input_rules.as_verified_rules()
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
        alice_rules = DMSInputRules.load(alice_spreadsheet).as_verified_rules()
        info_rules = DMSToInformation().transform(alice_rules)

        assert isinstance(info_rules, InformationRules)

    def test_dump_skip_default_space_and_version(self) -> None:
        dms_rules = DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator="Anders",
                created="2024-03-16",
                updated="2024-03-16",
            ),
            properties=[
                DMSInputProperty(
                    value_type="text",
                    container="Asset",
                    container_property="name",
                    view="WindFarm",
                    view_property="name",
                ),
            ],
            views=[
                DMSInputView(
                    view="WindFarm", implements="cdf_cdm:Sourceable(version=v1),cdf_cdm:Describable(version=v1)"
                ),
                DMSInputView(view="cdf_cdm:Sourceable(version=v1)"),
                DMSInputView(view="cdf_cdm:Describable(version=v1)"),
            ],
            containers=[DMSInputContainer(container="Asset", constraint="Sourceable,Describable")],
        ).as_verified_rules()

        normalize_neat_id_in_rules(dms_rules)

        expected_dump = {
            "metadata": {
                "role": "DMS Architect",
                "space": "my_space",
                "external_id": "my_data_model",
                "creator": "Anders",
                "created": datetime.datetime(2024, 3, 16),
                "updated": datetime.datetime(2024, 3, 16),
                "version": "1",
            },
            "properties": [
                {
                    "value_type": "text",
                    "container": "Asset",
                    "container_property": "name",
                    "view": "WindFarm",
                    "view_property": "name",
                    "neatId": "http://purl.org/cognite/neat/Property_0",
                }
            ],
            "views": [
                {
                    "view": "cdf_cdm:Describable(version=v1)",
                    "neatId": "http://purl.org/cognite/neat/View_2",
                },
                {
                    "view": "cdf_cdm:Sourceable(version=v1)",
                    "neatId": "http://purl.org/cognite/neat/View_1",
                },
                {
                    "view": "WindFarm",
                    "implements": "cdf_cdm:Sourceable(version=v1),cdf_cdm:Describable(version=v1)",
                    "neatId": "http://purl.org/cognite/neat/View_0",
                },
            ],
            "containers": [
                {
                    "container": "Asset",
                    "constraint": "Sourceable,Describable",
                    "neatId": "http://purl.org/cognite/neat/Container_0",
                }
            ],
        }

        actual_dump = dms_rules.dump(exclude_none=True, sort=True, exclude_unset=True, exclude_defaults=True)

        assert actual_dump == expected_dump

    def test_create_reference(self) -> None:
        info_rules = GraphData.car.get_care_rules()
        dms_rules = InformationToDMS().transform(info_rules)
        dms_rules = MapOneToOne(GraphData.car.BASE_MODEL, {"Manufacturer": "Entity", "Color": "Entity"}).transform(
            dms_rules
        )

        schema = dms_rules.as_schema()
        view_by_external_id = {view.external_id: view for view in schema.views.values()}
        # The Manufacturer and Color view only has one property, name, and this is
        # now expected to point to the Entity container in the base model.
        manufacturer_view = view_by_external_id["Manufacturer"]
        assert manufacturer_view.referenced_containers() == {
            dm.ContainerId(GraphData.car.BASE_MODEL.metadata.space, "Entity")
        }
        color_view = view_by_external_id["Color"]
        assert color_view.referenced_containers() == {dm.ContainerId(GraphData.car.BASE_MODEL.metadata.space, "Entity")}

    def test_metadata_int_version(self) -> None:
        raw_metadata = dict(
            space="some_space",
            external_id="some_id",
            creator="me",
            version=14,
            created="2024-03-16",
            updated="2024-03-16",
        )

        metadata = DMSMetadata.model_validate(raw_metadata)

        assert metadata.version == "14"

    def test_reverse_property(self) -> None:
        sub_core = DMSInputRules(
            DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                creator="Anders",
                version="v42",
            ),
            properties=[
                DMSInputProperty(
                    view="CogniteVisualizable",
                    view_property="object3D",
                    value_type="Cognite3DObject",
                    connection="direct",
                    max_count=1,
                    container="CogniteVisualizable",
                    container_property="object3D",
                ),
                DMSInputProperty(
                    view="Cognite3DObject",
                    view_property="asset",
                    value_type="CogniteVisualizable",
                    connection="reverse(property=object3D)",
                ),
            ],
            views=[
                DMSInputView(view="CogniteVisualizable"),
                DMSInputView(view="Cognite3DObject"),
            ],
            containers=[
                DMSInputContainer("CogniteVisualizable"),
            ],
        )
        with catch_issues() as issue_list:
            VerifyDMSRules().transform(ReadRules(sub_core, {}))

        assert not issue_list

    def test_reverse_property_in_parent(self) -> None:
        sub_core = DMSInputRules(
            DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                creator="Anders",
                version="v42",
            ),
            properties=[
                DMSInputProperty(
                    view="CogniteVisualizable",
                    view_property="object3D",
                    value_type="Cognite3DObject",
                    connection="direct",
                    max_count=1,
                    container="CogniteVisualizable",
                    container_property="object3D",
                ),
                DMSInputProperty(
                    view="Cognite3DObject",
                    view_property="asset",
                    value_type="CogniteAsset",
                    connection="reverse(property=object3D)",
                ),
            ],
            views=[
                DMSInputView(view="CogniteVisualizable"),
                DMSInputView(view="CogniteAsset", implements="CogniteVisualizable"),
                DMSInputView(view="Cognite3DObject"),
            ],
            containers=[
                DMSInputContainer("CogniteVisualizable"),
            ],
        )
        with catch_issues() as issues:
            _ = VerifyDMSRules().transform(ReadRules(sub_core, {}))

        assert not issues

    def test_subclass_parent_with_reverse_property(self) -> None:
        extended_core = DMSInputRules(
            DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                creator="Anders",
                version="v42",
            ),
            properties=[
                DMSInputProperty(
                    view="CogniteVisualizable",
                    view_property="object3D",
                    value_type="Cognite3DObject",
                    connection="direct",
                    max_count=1,
                    container="CogniteVisualizable",
                    container_property="object3D",
                ),
                DMSInputProperty(
                    view="Cognite3DObject",
                    view_property="asset",
                    value_type="CogniteAsset",
                    connection="reverse(property=object3D)",
                ),
            ],
            views=[
                DMSInputView(view="CogniteVisualizable"),
                DMSInputView(view="CogniteAsset", implements="CogniteVisualizable"),
                DMSInputView(view="Cognite3DObject"),
                DMSInputView(view="My3DObject", implements="Cognite3DObject"),
            ],
            containers=[
                DMSInputContainer("CogniteVisualizable"),
            ],
        )
        with catch_issues() as issues:
            rules = VerifyDMSRules().transform(ReadRules(extended_core, {}))

        assert not issues
        assert rules is not None

    def test_dump_dms_rules_keep_version(self) -> None:
        rules = DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                version="v1",
                creator="Anders",
            ),
            properties=[
                DMSInputProperty(
                    view="MyView",
                    view_property="name",
                    value_type="text",
                    container="cdf_cdm:CogniteDescribable",
                )
            ],
            views=[
                DMSInputView(view="MyView", implements="cdf_cdm:CogniteDescribable(version=v1)"),
                DMSInputView("cdf_cdm:CogniteDescribable(version=v1)"),
            ],
            containers=[DMSInputContainer("cdf_cdm:CogniteDescribable")],
        )
        verified = rules.as_verified_rules()

        assert isinstance(verified, DMSRules)

        dumped = verified.dump(entities_exclude_defaults=True)

        view_ids = {view["view"] for view in dumped["views"]}
        assert "cdf_cdm:CogniteDescribable(version=v1)" in view_ids


def edge_types_by_view_property_id_test_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                creator="Anders",
                version="v42",
            ),
            properties=[
                DMSInputProperty(
                    view="WindTurbine",
                    view_property="windFarm",
                    value_type="WindFarm",
                    connection="edge",
                    max_count=1,
                ),
                DMSInputProperty(
                    view="WindFarm",
                    view_property="windTurbines",
                    value_type="WindTurbine",
                    connection="edge(direction=inwards)",
                ),
            ],
            views=[
                DMSInputView(view="WindTurbine"),
                DMSInputView(view="WindFarm"),
            ],
        ),
        {
            (
                ViewEntity(space="my_space", externalId="WindTurbine", version="v42"),
                "windFarm",
            ): dm.DirectRelationReference(space="my_space", external_id="WindTurbine.windFarm"),
            (
                ViewEntity(space="my_space", externalId="WindFarm", version="v42"),
                "windTurbines",
            ): dm.DirectRelationReference(space="my_space", external_id="WindTurbine.windFarm"),
        },
        id="Indirect edge use outwards type",
    )

    yield pytest.param(
        DMSInputRules(
            metadata=DMSInputMetadata(
                space="my_space",
                external_id="my_data_model",
                creator="Anders",
                version="v42",
            ),
            properties=[
                DMSInputProperty(
                    view="EnergyArea",
                    view_property="units",
                    value_type="GeneratingUnit",
                    connection="edge",
                    max_count=1,
                ),
                DMSInputProperty(
                    view="WindFarm",
                    view_property="units",
                    value_type="WindTurbine",
                    connection="edge",
                ),
            ],
            views=[
                DMSInputView(view="EnergyArea"),
                DMSInputView(view="WindFarm", implements="EnergyArea"),
            ],
        ),
        {
            (ViewEntity(space="my_space", externalId="EnergyArea", version="v42"), "units"): dm.DirectRelationReference(
                space="my_space", external_id="EnergyArea.units"
            ),
            (ViewEntity(space="my_space", externalId="WindFarm", version="v42"), "units"): dm.DirectRelationReference(
                space="my_space", external_id="EnergyArea.units"
            ),
        },
        id="Child uses parent edge",
    )


class TestDMSExporter:
    def test_svein_harald_as_schema(self, svein_harald_dms_rules: DMSRules) -> None:
        expected_views = {"GeneratingUnit", "EnergyArea", "TimeseriesForecastProduct"}
        expected_model_views = expected_views

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

        # before it was pulling extra containers from Last rules
        expected_containers = set()

        schema = olav_rebuild_dms_rules.as_schema()

        actual_views = {view.external_id for view in schema.views}
        assert actual_views == expected_views
        actual_model_views = {view.external_id for view in schema.data_model.views}
        assert actual_model_views == expected_views
        actual_containers = {container.external_id for container in schema.containers}
        assert actual_containers == expected_containers

    @pytest.mark.parametrize(
        "raw, expected_edge_types_by_view_property_id", list(edge_types_by_view_property_id_test_cases())
    )
    def test_edge_types_by_view_property_id(
        self,
        raw: DMSInputRules,
        expected_edge_types_by_view_property_id: dict[tuple[ViewEntity, str], dm.DirectRelationReference],
    ) -> None:
        dms_rules = DMSRules.model_validate(raw.dump())
        view_by_id = {view.view: view for view in dms_rules.views}
        properties_by_view_id: dict[dm.ViewId, list[DMSProperty]] = defaultdict(list)
        for prop in dms_rules.properties:
            properties_by_view_id[prop.view.as_id()].append(prop)

        exporter = _DMSExporter(dms_rules)

        actual = exporter._edge_types_by_view_property_id(properties_by_view_id, view_by_id)

        assert actual == expected_edge_types_by_view_property_id


class TestDMSValidation:
    @pytest.mark.parametrize(
        "input_rules, expected_views, expected_containers",
        [
            pytest.param(
                DMSInputRules(
                    DMSInputMetadata("my_space", "MyModel", "Me", "v1"),
                    properties=[
                        DMSInputProperty("MyView", "name", "text", container="MyContainer", container_property="name"),
                    ],
                    views=[DMSInputView("MyView")],
                    containers=[DMSInputContainer("MyContainer", constraint="cdf_cdm:CogniteDescribable")],
                ),
                set(),
                {ContainerEntity(space="cdf_cdm", externalId="CogniteDescribable")},
                id="Container requiring other container",
            )
        ],
    )
    def test_imported_views_and_containers_ids(
        self, input_rules: DMSInputRules, expected_views: set[ViewEntity], expected_containers: set[ContainerEntity]
    ) -> None:
        validation = DMSValidation(input_rules.as_verified_rules())
        actual_views, actual_containers = validation.imported_views_and_containers_ids()

        assert actual_views == expected_views
        assert actual_containers == expected_containers


class TestDMSProperty:
    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param(
                DMSInputProperty(
                    "sp:MyView(version=v1)",
                    "isOn",
                    "boolean",
                    default=1.0,
                ),
                id="Boolean with default 1.0 (reading from excel with pandas can lead TRUE to be read as 1.0)",
            )
        ],
    )
    def test_model_validate(self, raw: DMSInputProperty):
        prop = DMSProperty.model_validate(raw.dump("sp", "v1"))
        assert prop.model_dump(exclude_unset=True)

    @pytest.mark.parametrize(
        "raw, expected_msg",
        [
            pytest.param(
                DMSInputProperty(
                    "sp:MyView(version=v1)",
                    "enterprise",
                    value_type="sp:OtherView(version=v1)",
                    connection=None,
                ),
                "Value error, Missing connection type for property 'enterprise'. "
                "This is required with value type pointing to another view.",
                id="Missing connection specification",
            )
        ],
    )
    def test_model_validate_invalid(self, raw: DMSInputProperty, expected_msg: str):
        with pytest.raises(ValidationError) as e:
            _ = DMSProperty.model_validate(raw.dump("sp", "v1"))

        errors = e.value.errors()
        assert len(errors) == 1
        error = errors[0]
        assert error["msg"] == expected_msg
