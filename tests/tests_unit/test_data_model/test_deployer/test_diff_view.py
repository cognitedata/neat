import pytest

from cognite.neat._data_model.deployer._differ_view import (
    ViewDiffer,
    ViewPropertyDiffer,
)
from cognite.neat._data_model.deployer.data_classes import (
    AddedProperty,
    ContainerPropertyChange,
    PrimitivePropertyChange,
    PropertyChange,
    RemovedProperty,
    SeverityType,
)
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    MultiEdgeProperty,
    NodeReference,
    SingleReverseDirectRelationPropertyRequest,
    ViewCorePropertyRequest,
    ViewDirectReference,
    ViewReference,
    ViewRequest,
)


class TestViewDiffer:
    cdf_view = ViewRequest(
        space="test_space",
        externalId="test_view",
        version="1",
        name="Test View",
        description="This is a test view.",
        filter={"equals": {"property": ["node", "type"], "value": "TestNode"}},
        implements=[ViewReference(space="core", external_id="base_view", version="1")],
        properties={
            "toModify": ViewCorePropertyRequest(
                container=ContainerReference(space="test_space", external_id="test_container"),
                containerPropertyIdentifier="name",
            ),
            "toRemove": ViewCorePropertyRequest(
                container=ContainerReference(space="test_space", external_id="test_container"),
                containerPropertyIdentifier="description",
            ),
        },
    )

    changed_view = ViewRequest(
        space="test_space",
        externalId="test_view",
        version="1",
        name="Updated Test View",
        description="This is an updated view.",
        filter={"equals": {"property": ["node", "status"], "value": "Active"}},
        implements=[
            ViewReference(space="core", external_id="base_view", version="1"),
            ViewReference(space="core", external_id="extra_view", version="2"),
        ],
        properties={
            "toModify": ViewCorePropertyRequest(
                container=ContainerReference(space="test_space", external_id="test_container"),
                containerPropertyIdentifier="anotherProperty",
            ),
            "toAdd": MultiEdgeProperty(
                source=ViewReference(space="target_space", external_id="target_view", version="1"),
                type=NodeReference(space="node_space", external_id="node_type"),
                direction="outwards",
            ),
        },
    )

    @pytest.mark.parametrize(
        "resource,expected_diff",
        [
            pytest.param(
                cdf_view,
                [],
                id="no changes",
            ),
            pytest.param(
                changed_view,
                [
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Test View",
                        new_value="Updated Test View",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="This is a test view.",
                        new_value="This is an updated view.",
                    ),
                    PrimitivePropertyChange(
                        field_path="filter",
                        item_severity=SeverityType.BREAKING,
                        old_value=str(cdf_view.filter),
                        new_value=str(changed_view.filter),
                    ),
                    PrimitivePropertyChange(
                        field_path="implements",
                        item_severity=SeverityType.BREAKING,
                        old_value=str(cdf_view.implements),
                        new_value=str(changed_view.implements),
                    ),
                    AddedProperty(
                        field_path="properties.toAdd",
                        item_severity=SeverityType.SAFE,
                        new_value=changed_view.properties["toAdd"],  # type: ignore[index]
                    ),
                    RemovedProperty(
                        field_path="properties.toRemove",
                        item_severity=SeverityType.BREAKING,
                        old_value=cdf_view.properties["toRemove"],  # type: ignore[index]
                    ),
                    ContainerPropertyChange(
                        field_path="properties.toModify",
                        changed_items=[
                            PrimitivePropertyChange(
                                field_path="containerPropertyIdentifier",
                                item_severity=SeverityType.BREAKING,
                                old_value="name",
                                new_value="anotherProperty",
                            ),
                        ],
                    ),
                ],
                id="Modify/Add/Remove properties, filter, implements",
            ),
        ],
    )
    def test_view_diff(self, resource: ViewRequest, expected_diff: list[PropertyChange]) -> None:
        actual_diffs = ViewDiffer().diff(self.cdf_view, resource)
        assert expected_diff == actual_diffs

    @pytest.mark.parametrize(
        "cdf_property,desired_property,expected_diff",
        [
            pytest.param(
                ViewCorePropertyRequest(
                    container=ContainerReference(space="space_a", external_id="container_a"),
                    containerPropertyIdentifier="prop_a",
                    name="Property A",
                    description="Description A",
                    source=ViewReference(space="view_space", external_id="view_a", version="1"),
                ),
                ViewCorePropertyRequest(
                    container=ContainerReference(space="space_b", external_id="container_b"),
                    containerPropertyIdentifier="prop_b",
                    name="Property B",
                    description="Description B",
                    source=ViewReference(space="view_space", external_id="view_b", version="2"),
                ),
                [
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Property A",
                        new_value="Property B",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="Description A",
                        new_value="Description B",
                    ),
                    PrimitivePropertyChange(
                        field_path="container",
                        item_severity=SeverityType.BREAKING,
                        old_value=ContainerReference(space="space_a", external_id="container_a"),
                        new_value=ContainerReference(space="space_b", external_id="container_b"),
                    ),
                    PrimitivePropertyChange(
                        field_path="containerPropertyIdentifier",
                        item_severity=SeverityType.BREAKING,
                        old_value="prop_a",
                        new_value="prop_b",
                    ),
                    PrimitivePropertyChange(
                        field_path="source",
                        item_severity=SeverityType.BREAKING,
                        old_value=ViewReference(space="view_space", external_id="view_a", version="1"),
                        new_value=ViewReference(space="view_space", external_id="view_b", version="2"),
                    ),
                ],
                id="ViewCoreProperty change",
            ),
            pytest.param(
                MultiEdgeProperty(
                    source=ViewReference(space="source_space", external_id="source_view", version="1"),
                    type=NodeReference(space="node_space_a", external_id="node_type_a"),
                    edgeSource=ViewReference(space="edge_space", external_id="edge_view", version="1"),
                    direction="outwards",
                    name="Edges",
                    description="Edge connection",
                ),
                MultiEdgeProperty(
                    source=ViewReference(space="source_space", external_id="updated_source_view", version="2"),
                    type=NodeReference(space="node_space_b", external_id="node_type_b"),
                    edgeSource=ViewReference(space="edge_space", external_id="updated_edge_view", version="2"),
                    direction="inwards",
                    name="Updated Edges",
                    description="Updated edge connection",
                ),
                [
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Edges",
                        new_value="Updated Edges",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="Edge connection",
                        new_value="Updated edge connection",
                    ),
                    PrimitivePropertyChange(
                        field_path="source",
                        item_severity=SeverityType.BREAKING,
                        old_value=ViewReference(space="source_space", external_id="source_view", version="1"),
                        new_value=ViewReference(space="source_space", external_id="updated_source_view", version="2"),
                    ),
                    PrimitivePropertyChange(
                        field_path="type",
                        item_severity=SeverityType.BREAKING,
                        old_value=NodeReference(space="node_space_a", external_id="node_type_a"),
                        new_value=NodeReference(space="node_space_b", external_id="node_type_b"),
                    ),
                    PrimitivePropertyChange(
                        field_path="edgeSource",
                        item_severity=SeverityType.BREAKING,
                        old_value=ViewReference(space="edge_space", external_id="edge_view", version="1"),
                        new_value=ViewReference(space="edge_space", external_id="updated_edge_view", version="2"),
                    ),
                    PrimitivePropertyChange(
                        field_path="direction",
                        item_severity=SeverityType.BREAKING,
                        old_value="outwards",
                        new_value="inwards",
                    ),
                ],
                id="EdgeProperty change",
            ),
            pytest.param(
                SingleReverseDirectRelationPropertyRequest(
                    source=ViewReference(space="relation_space", external_id="relation_view", version="1"),
                    through=ViewDirectReference(
                        source=ViewReference(space="through_space", external_id="through_view", version="1"),
                        identifier="relation_id",
                    ),
                    name="Reverse Relation",
                    description="A reverse direct relation",
                ),
                SingleReverseDirectRelationPropertyRequest(
                    source=ViewReference(space="relation_space", external_id="updated_relation_view", version="2"),
                    through=ViewDirectReference(
                        source=ViewReference(space="through_space", external_id="updated_through_view", version="2"),
                        identifier="updated_relation_id",
                    ),
                    name="Updated Reverse Relation",
                    description="An updated reverse direct relation",
                ),
                [
                    PrimitivePropertyChange(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        old_value="Reverse Relation",
                        new_value="Updated Reverse Relation",
                    ),
                    PrimitivePropertyChange(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        old_value="A reverse direct relation",
                        new_value="An updated reverse direct relation",
                    ),
                    PrimitivePropertyChange(
                        field_path="source",
                        item_severity=SeverityType.BREAKING,
                        old_value=ViewReference(space="relation_space", external_id="relation_view", version="1"),
                        new_value=ViewReference(
                            space="relation_space", external_id="updated_relation_view", version="2"
                        ),
                    ),
                    PrimitivePropertyChange(
                        field_path="through",
                        item_severity=SeverityType.BREAKING,
                        old_value=ViewDirectReference(
                            source=ViewReference(space="through_space", external_id="through_view", version="1"),
                            identifier="relation_id",
                        ),
                        new_value=ViewDirectReference(
                            source=ViewReference(
                                space="through_space", external_id="updated_through_view", version="2"
                            ),
                            identifier="updated_relation_id",
                        ),
                    ),
                ],
                id="ReverseDirectRelationProperty change",
            ),
            pytest.param(
                ViewCorePropertyRequest(
                    container=ContainerReference(space="space_a", external_id="container_a"),
                    containerPropertyIdentifier="prop_a",
                ),
                MultiEdgeProperty(
                    source=ViewReference(space="source_space", external_id="source_view", version="1"),
                    type=NodeReference(space="node_space", external_id="node_type"),
                    direction="outwards",
                ),
                [
                    PrimitivePropertyChange(
                        field_path="connectionType",
                        item_severity=SeverityType.BREAKING,
                        old_value="primary_property",
                        new_value="multi_edge_connection",
                    )
                ],
                id="Different property types",
            ),
        ],
    )
    def test_view_property_diff(
        self,
        cdf_property: ViewCorePropertyRequest | MultiEdgeProperty | SingleReverseDirectRelationPropertyRequest,
        desired_property: ViewCorePropertyRequest | MultiEdgeProperty | SingleReverseDirectRelationPropertyRequest,
        expected_diff: list[PropertyChange],
    ) -> None:
        actual = ViewPropertyDiffer().diff(cdf_property, desired_property)
        assert expected_diff == actual
