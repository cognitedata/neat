import pytest

from cognite.neat._data_model.deployer._differ_view import (
    ViewDiffer,
    ViewPropertyDiffer,
)
from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    FieldChanges,
    RemovedField,
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
    TO_MODIFY_ID = "toModify"
    cdf_view = ViewRequest(
        space="test_space",
        externalId="test_view",
        version="1",
        name="Test View",
        description="This is a test view.",
        filter={"equals": {"property": ["node", "type"], "value": "TestNode"}},
        implements=[ViewReference(space="core", external_id="base_view", version="1")],
        properties={
            TO_MODIFY_ID: ViewCorePropertyRequest(
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
            TO_MODIFY_ID: ViewCorePropertyRequest(
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
                    AddedField(
                        field_path="implements",
                        item_severity=SeverityType.BREAKING,
                        new_value=changed_view.implements[1],  # type: ignore[index]
                    ),
                    ChangedField(
                        field_path="name",
                        item_severity=SeverityType.SAFE,
                        current_value="Test View",
                        new_value="Updated Test View",
                    ),
                    ChangedField(
                        field_path="description",
                        item_severity=SeverityType.SAFE,
                        current_value="This is a test view.",
                        new_value="This is an updated view.",
                    ),
                    ChangedField(
                        field_path="filter",
                        item_severity=SeverityType.WARNING,
                        current_value=str(cdf_view.filter),
                        new_value=str(changed_view.filter),
                    ),
                    AddedField(
                        field_path="properties.toAdd",
                        item_severity=SeverityType.SAFE,
                        new_value=changed_view.properties["toAdd"],  # type: ignore[index]
                    ),
                    RemovedField(
                        field_path="properties.toRemove",
                        item_severity=SeverityType.BREAKING,
                        current_value=cdf_view.properties["toRemove"],  # type: ignore[index]
                    ),
                    FieldChanges(
                        field_path=f"properties.{TO_MODIFY_ID}",
                        changes=[
                            ChangedField(
                                field_path=f"properties.{TO_MODIFY_ID}.containerPropertyIdentifier",
                                item_severity=SeverityType.BREAKING,
                                current_value="name",
                                new_value="anotherProperty",
                            ),
                        ],
                    ),
                ],
                id="Modify/Add/Remove properties, filter, implements",
            ),
        ],
    )
    def test_view_diff(self, resource: ViewRequest, expected_diff: list[FieldChange]) -> None:
        actual_diffs = ViewDiffer(
            current_container_map={},
            new_container_map={},
        ).diff(self.cdf_view, resource)
        assert expected_diff == actual_diffs

    VIEW_PROPERTY_ID = "property_id"

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
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.name",
                        item_severity=SeverityType.SAFE,
                        current_value="Property A",
                        new_value="Property B",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.description",
                        item_severity=SeverityType.SAFE,
                        current_value="Description A",
                        new_value="Description B",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.container",
                        item_severity=SeverityType.BREAKING,
                        current_value=ContainerReference(space="space_a", external_id="container_a"),
                        new_value=ContainerReference(space="space_b", external_id="container_b"),
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.containerPropertyIdentifier",
                        item_severity=SeverityType.BREAKING,
                        current_value="prop_a",
                        new_value="prop_b",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.source",
                        item_severity=SeverityType.BREAKING,
                        current_value=ViewReference(space="view_space", external_id="view_a", version="1"),
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
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.name",
                        item_severity=SeverityType.SAFE,
                        current_value="Edges",
                        new_value="Updated Edges",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.description",
                        item_severity=SeverityType.SAFE,
                        current_value="Edge connection",
                        new_value="Updated edge connection",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.source",
                        item_severity=SeverityType.BREAKING,
                        current_value=ViewReference(space="source_space", external_id="source_view", version="1"),
                        new_value=ViewReference(space="source_space", external_id="updated_source_view", version="2"),
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.type",
                        item_severity=SeverityType.WARNING,
                        current_value=NodeReference(space="node_space_a", external_id="node_type_a"),
                        new_value=NodeReference(space="node_space_b", external_id="node_type_b"),
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.edgeSource",
                        item_severity=SeverityType.WARNING,
                        current_value=ViewReference(space="edge_space", external_id="edge_view", version="1"),
                        new_value=ViewReference(space="edge_space", external_id="updated_edge_view", version="2"),
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.direction",
                        item_severity=SeverityType.WARNING,
                        current_value="outwards",
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
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.name",
                        item_severity=SeverityType.SAFE,
                        current_value="Reverse Relation",
                        new_value="Updated Reverse Relation",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.description",
                        item_severity=SeverityType.SAFE,
                        current_value="A reverse direct relation",
                        new_value="An updated reverse direct relation",
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.source",
                        item_severity=SeverityType.BREAKING,
                        current_value=ViewReference(space="relation_space", external_id="relation_view", version="1"),
                        new_value=ViewReference(
                            space="relation_space", external_id="updated_relation_view", version="2"
                        ),
                    ),
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.through",
                        item_severity=SeverityType.WARNING,
                        current_value=ViewDirectReference(
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
                    ChangedField(
                        field_path=f"{VIEW_PROPERTY_ID}.connectionType",
                        item_severity=SeverityType.BREAKING,
                        current_value="primary_property",
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
        expected_diff: list[ChangedField],
    ) -> None:
        actual = ViewPropertyDiffer(current_container_map={}, new_container_map={}).diff(
            cdf_property, desired_property, self.VIEW_PROPERTY_ID
        )
        assert expected_diff == actual
