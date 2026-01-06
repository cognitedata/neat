from collections.abc import Iterable
from typing import cast
from uuid import uuid4

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model.deployer._differ_view import ViewDiffer
from cognite.neat._data_model.deployer.data_classes import (
    humanize_changes,
)
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DirectNodeRelation,
    EqualsFilterData,
    Int32Property,
    MultiEdgeProperty,
    MultiReverseDirectRelationPropertyRequest,
    NodeReference,
    SingleEdgeProperty,
    SingleReverseDirectRelationPropertyRequest,
    SpaceResponse,
    TextProperty,
    ViewCorePropertyRequest,
    ViewDirectReference,
    ViewReference,
    ViewRequest,
)

from .utils import assert_allowed_change, assert_change

CORE_PROPERTY_ID = "coreProperty"
EDGE_PROPERTY_ID = "edgeProperty"
REVERSE_DIRECT_RELATION_PROPERTY_ID = "reverseDirectRelationProperty"
DIRECT_PROPERTY_ID = "directProperty"


@pytest.fixture(scope="module")
def supporting_container(neat_test_space: SpaceResponse, neat_client: NeatClient) -> Iterable[ContainerRequest]:
    """Create a container that will be used by the view properties."""
    random_id = str(uuid4()).replace("-", "_")
    container = ContainerRequest(
        space=neat_test_space.space,
        externalId=f"test_view_container_{random_id}",
        name="Supporting Container",
        description="Container for view property testing",
        usedFor="node",
        properties={
            "textProp": ContainerPropertyDefinition(
                type=TextProperty(),
                nullable=True,
            ),
            "anotherTextProp": ContainerPropertyDefinition(type=TextProperty(), nullable=True),
            "intProp": ContainerPropertyDefinition(type=Int32Property(), nullable=True),
            "directProp": ContainerPropertyDefinition(type=DirectNodeRelation(), nullable=True),
        },
    )
    try:
        created = neat_client.containers.apply([container])
        if len(created) != 1:
            raise AssertionError(
                "Failed to set up supporting container for testing how the view API reacts to changes."
            )
        yield created[0].as_request()
    finally:
        neat_client.containers.delete([container.as_reference()])


@pytest.fixture(scope="module")
def supporting_container2(neat_test_space: SpaceResponse, neat_client: NeatClient) -> Iterable[ContainerRequest]:
    """Create a container that will be used by the view properties."""
    random_id = str(uuid4()).replace("-", "_")
    container = ContainerRequest(
        space=neat_test_space.space,
        externalId=f"test_view_container2_{random_id}",
        name="Supporting Container 2 ",
        description="Container for view property testing",
        usedFor="node",
        properties={
            "textProp": ContainerPropertyDefinition(type=TextProperty(), nullable=True),
            "directProp": ContainerPropertyDefinition(type=DirectNodeRelation()),
        },
    )
    try:
        created = neat_client.containers.apply([container])
        if len(created) != 1:
            raise AssertionError(
                "Failed to set up supporting containers for testing how the view API reacts to changes."
            )
        yield created[0].as_request()
    finally:
        neat_client.containers.delete([container.as_reference()])


@pytest.fixture(scope="module")
def supporting_edge_container(neat_test_space: SpaceResponse, neat_client: NeatClient) -> Iterable[ContainerRequest]:
    """Create a container that will be used by the view properties."""
    random_id = str(uuid4()).replace("-", "_")
    container = ContainerRequest(
        space=neat_test_space.space,
        externalId=f"test_edge_container_{random_id}",
        name="Supporting Edge Container",
        description="Container for view property testing",
        usedFor="edge",
        properties={
            "edgeProp": ContainerPropertyDefinition(
                type=TextProperty(),
                nullable=True,
            ),
        },
    )
    try:
        created = neat_client.containers.apply([container])
        if len(created) != 1:
            raise AssertionError(
                "Failed to set up supporting edge container for testing how the view API reacts to changes."
            )
        yield created[0].as_request()
    finally:
        neat_client.containers.delete([container.as_reference()])


@pytest.fixture(scope="module")
def supporting_view(
    neat_test_space: SpaceResponse, neat_client: NeatClient, supporting_container: ContainerRequest
) -> Iterable[ViewRequest]:
    """Create a view that will be used as source for edge and reverse relation properties."""
    random_id = str(uuid4()).replace("-", "_")
    view = ViewRequest(
        space=neat_test_space.space,
        externalId=f"test_supporting_view_{random_id}",
        version="v1",
        name="Supporting View",
        description="View for property testing",
        properties={
            "textProp": ViewCorePropertyRequest(
                container=supporting_container.as_reference(),
                containerPropertyIdentifier="textProp",
            ),
            "directProp": ViewCorePropertyRequest(
                container=supporting_container.as_reference(),
                containerPropertyIdentifier="directProp",
            ),
        },
    )
    try:
        created = neat_client.views.apply([view])
        if len(created) != 1:
            raise AssertionError("Failed to set up supporting view for testing how the view API reacts to changes.")
        yield created[0].as_request()
    finally:
        neat_client.views.delete([view.as_reference()])


@pytest.fixture(scope="module")
def supporting_view2(
    neat_test_space: SpaceResponse,
    neat_client: NeatClient,
    supporting_container2: ContainerRequest,
    supporting_view: ViewRequest,
) -> Iterable[ViewRequest]:
    """Create a view that will be used as source for edge and reverse relation properties."""
    random_id = str(uuid4()).replace("-", "_")
    view = ViewRequest(
        space=neat_test_space.space,
        externalId=f"test_supporting_view2_{random_id}",
        version="v1",
        name="Supporting View 2",
        description="View for property testing",
        properties={
            "textProp": ViewCorePropertyRequest(
                container=supporting_container2.as_reference(),
                containerPropertyIdentifier="textProp",
            ),
            "directProp": ViewCorePropertyRequest(
                container=supporting_container2.as_reference(),
                containerPropertyIdentifier="directProp",
                source=supporting_view.as_reference(),
            ),
        },
    )
    try:
        created = neat_client.views.apply([view])
        if len(created) != 1:
            raise AssertionError("Failed to set up supporting views for testing how the view API reacts to changes.")
        yield created[0].as_request()
    finally:
        neat_client.views.delete([view.as_reference()])


@pytest.fixture(scope="module")
def supporting_edge_view(
    neat_test_space: SpaceResponse,
    neat_client: NeatClient,
    supporting_edge_container: ContainerRequest,
) -> Iterable[ViewRequest]:
    """Create a view that will be used as edge source for edge properties."""
    random_id = str(uuid4()).replace("-", "_")
    view = ViewRequest(
        space=neat_test_space.space,
        externalId=f"test_supporting_edge_view_{random_id}",
        version="v1",
        name="Supporting Edge View",
        description="View for edge property testing",
        properties={
            "edgeProp": ViewCorePropertyRequest(
                container=supporting_edge_container.as_reference(),
                containerPropertyIdentifier="edgeProp",
            ),
        },
    )
    try:
        created = neat_client.views.apply([view])
        if len(created) != 1:
            raise AssertionError(
                "Failed to set up supporting edge view for testing how the view API reacts to changes."
            )
        yield created[0].as_request()
    finally:
        neat_client.views.delete([view.as_reference()])


@pytest.fixture(scope="module")
def supporting_edge_view2(
    neat_test_space: SpaceResponse,
    neat_client: NeatClient,
    supporting_edge_container: ContainerRequest,
) -> Iterable[ViewRequest]:
    """Create a view that will be used as edge source for edge properties."""
    random_id = str(uuid4()).replace("-", "_")
    view = ViewRequest(
        space=neat_test_space.space,
        externalId=f"test_supporting_edge_view2_{random_id}",
        version="v1",
        name="Supporting Edge View 2",
        description="View for edge property testing",
        properties={
            "edgeProp": ViewCorePropertyRequest(
                container=supporting_edge_container.as_reference(),
                containerPropertyIdentifier="edgeProp",
            ),
        },
    )
    try:
        created = neat_client.views.apply([view])
        if len(created) != 1:
            raise AssertionError(
                "Failed to set up supporting edge view for testing how the view API reacts to changes."
            )
        yield created[0].as_request()
    finally:
        neat_client.views.delete([view.as_reference()])


@pytest.fixture(scope="function")
def current_view(
    neat_test_space: SpaceResponse,
    neat_client: NeatClient,
    supporting_container: ContainerRequest,
    supporting_view: ViewRequest,
    supporting_edge_view: ViewRequest,
) -> Iterable[ViewRequest]:
    """This is the view in CDF before changes."""
    random_id = str(uuid4()).replace("-", "_")
    view = ViewRequest(
        space=neat_test_space.space,
        externalId=f"test_view_{random_id}",
        version="v1",
        name="Initial name",
        description="Initial description",
        filter={"equals": EqualsFilterData(property=["node", "space"], value=neat_test_space.space)},
        implements=[
            ViewReference(space="cdf_cdm", external_id="CogniteDescribable", version="v1"),
            ViewReference(space="cdf_cdm", external_id="CogniteSchedulable", version="v1"),
        ],
        properties={
            CORE_PROPERTY_ID: ViewCorePropertyRequest(
                name="Core Property",
                description="A core property",
                container=supporting_container.as_reference(),
                containerPropertyIdentifier="textProp",
            ),
            DIRECT_PROPERTY_ID: ViewCorePropertyRequest(
                name="Direct Property",
                description="A direct relation property",
                container=supporting_container.as_reference(),
                containerPropertyIdentifier="directProp",
                source=supporting_view.as_reference(),
            ),
            EDGE_PROPERTY_ID: SingleEdgeProperty(
                name="Edge Property",
                description="An edge property",
                source=supporting_view.as_reference(),
                type=NodeReference(space=neat_test_space.space, external_id="NodeType"),
                edgeSource=supporting_edge_view.as_reference(),
                direction="outwards",
            ),
            REVERSE_DIRECT_RELATION_PROPERTY_ID: SingleReverseDirectRelationPropertyRequest(
                name="Reverse Direct Relation",
                description="A reverse direct relation property",
                source=supporting_view.as_reference(),
                through=ViewDirectReference(
                    source=supporting_view.as_reference(),
                    identifier="directProp",
                ),
            ),
        },
    )
    try:
        created = neat_client.views.apply([view])
        if len(created) != 1:
            raise AssertionError("Failed to set up a view for testing how the view API reacts to changes.")
        created_view = created[0]
        yield created_view.as_request()
    finally:
        neat_client.views.delete([view.as_reference()])


@pytest.fixture(scope="module")
def all_supporting_containers(
    supporting_container: ContainerRequest,
    supporting_container2: ContainerRequest,
    supporting_edge_container: ContainerRequest,
) -> dict[ContainerReference, ContainerRequest]:
    """Fixture to ensure all supporting containers are created before tests run."""
    return {
        supporting_container.as_reference(): supporting_container,
        supporting_container2.as_reference(): supporting_container2,
        supporting_edge_container.as_reference(): supporting_edge_container,
    }


class TestViewDiffer:
    def test_diff_no_changes(
        self,
        current_view: ViewRequest,
        neat_client: NeatClient,
        all_supporting_containers: dict[ContainerReference, ContainerRequest],
    ) -> None:
        new_view = current_view.model_copy(deep=True)
        diffs = ViewDiffer(all_supporting_containers, all_supporting_containers).diff(current_view, new_view)
        if len(diffs) != 0:
            messages = humanize_changes(diffs)
            raise AssertionError(f"Updating a view without changes should yield no diffs. Got:\n{messages}")

        assert_allowed_change(new_view, neat_client.views, "no changes", expect_silent_ignore=False)

    def test_diff_name(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        new_view = current_view.model_copy(deep=True, update={"name": "Updated name"})
        assert_change(ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path="name")

    def test_diff_description(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        new_view = current_view.model_copy(deep=True, update={"description": "Updated description"})
        assert_change(ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path="description")

    def test_diff_filter(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        new_view = current_view.model_copy(
            deep=True,
            update={"filter": {"equals": {"property": ["node", "externalId"], "value": "something"}}},
        )
        assert_change(ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path="filter")

    def test_diff_implements_add(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        new_implements = (current_view.implements or []) + [
            ViewReference(space="cdf_cdm", external_id="CogniteSourceable", version="v1")
        ]
        new_view = current_view.model_copy(deep=True, update={"implements": new_implements})
        assert_change(ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path="implements")

    def test_diff_implements_remove(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        if current_view.implements is None or len(current_view.implements) == 0:
            raise AssertionError(
                "The test view should have implements configured, but none were found. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_implements = current_view.implements[:-1] if len(current_view.implements) > 1 else []
        new_view = current_view.model_copy(deep=True, update={"implements": new_implements})
        assert_change(ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path="implements")

    def test_diff_implements_order(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        if current_view.implements is None or len(current_view.implements) < 2:
            raise AssertionError(
                "The test view should have at least two implements configured for this test, but it does not. "
                "The test setup may have changed or the API may be returning different default values."
            )
        new_implements = list(reversed(current_view.implements))
        new_view = current_view.model_copy(deep=True, update={"implements": new_implements})
        assert_change(ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path="implements")

    def test_add_property(
        self, current_view: ViewRequest, supporting_container: ContainerRequest, neat_client: NeatClient
    ) -> None:
        new_property_id = "newProperty"
        new_property = ViewCorePropertyRequest(
            name="New Property",
            container=supporting_container.as_reference(),
            containerPropertyIdentifier="textProp",
        )
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, new_property_id: new_property}}
        )

        assert_change(
            ViewDiffer({}, {}), current_view, new_view, neat_client.views, field_path=f"properties.{new_property_id}"
        )

    def test_remove_property(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        new_properties = current_view.properties.copy()
        del new_properties[CORE_PROPERTY_ID]
        new_view = current_view.model_copy(update={"properties": new_properties})

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{CORE_PROPERTY_ID}",
            expect_silent_ignore=True,
            neat_override_breaking_changes=True,
        )


class TestViewCorePropertyDiffer:
    def test_diff_container_same_property_type(
        self,
        current_view: ViewRequest,
        neat_test_space: SpaceResponse,
        neat_client: NeatClient,
        supporting_container2: ContainerRequest,
        all_supporting_containers: dict[ContainerReference, ContainerRequest],
    ) -> None:
        core_property = cast(ViewCorePropertyRequest, current_view.properties[CORE_PROPERTY_ID])
        new_core_property = core_property.model_copy(
            deep=True, update={"container": supporting_container2.as_reference()}
        )
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, CORE_PROPERTY_ID: new_core_property}}
        )

        assert_change(
            ViewDiffer(all_supporting_containers, all_supporting_containers),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{CORE_PROPERTY_ID}.container",
        )

    def test_diff_container_property_identifier_same_property_type(
        self,
        current_view: ViewRequest,
        neat_client: NeatClient,
        all_supporting_containers: dict[ContainerReference, ContainerRequest],
    ) -> None:
        core_property = cast(ViewCorePropertyRequest, current_view.properties[CORE_PROPERTY_ID])
        new_core_property = core_property.model_copy(
            deep=True, update={"container_property_identifier": "anotherTextProp"}
        )

        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, CORE_PROPERTY_ID: new_core_property}}
        )

        assert_change(
            ViewDiffer(all_supporting_containers, all_supporting_containers),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{CORE_PROPERTY_ID}.containerPropertyIdentifier",
        )

    def test_diff_container_property_identifier_change_property_type(
        self,
        current_view: ViewRequest,
        neat_client: NeatClient,
        all_supporting_containers: dict[ContainerReference, ContainerRequest],
    ) -> None:
        core_property = cast(ViewCorePropertyRequest, current_view.properties[CORE_PROPERTY_ID])
        new_core_property = core_property.model_copy(deep=True, update={"container_property_identifier": "intProp"})

        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, CORE_PROPERTY_ID: new_core_property}}
        )

        assert_change(
            ViewDiffer(all_supporting_containers, all_supporting_containers),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{CORE_PROPERTY_ID}.containerPropertyIdentifier",
            in_error_message=f"property '{CORE_PROPERTY_ID}' would change type",
        )

    def test_diff_source(
        self, current_view: ViewRequest, supporting_view2: ViewRequest, neat_client: NeatClient
    ) -> None:
        direct_property = cast(ViewCorePropertyRequest, current_view.properties[DIRECT_PROPERTY_ID])
        new_direct_property = direct_property.model_copy(deep=True, update={"source": supporting_view2.as_reference()})
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, DIRECT_PROPERTY_ID: new_direct_property}}
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{DIRECT_PROPERTY_ID}.source",
        )


class TestViewEdgePropertyDiffer:
    def test_diff_connection_type(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        single_edge = cast(SingleEdgeProperty, current_view.properties[EDGE_PROPERTY_ID])
        # Change from single edge to multi edge
        new_multi_edge = MultiEdgeProperty.model_validate(
            single_edge.model_dump(by_alias=True, exclude={"connection_type"})
        )
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, EDGE_PROPERTY_ID: new_multi_edge}}
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{EDGE_PROPERTY_ID}.connectionType",
            in_error_message="'edgeProperty' would change type from single_edge_connection to multi_edge_connection",
        )

    def test_diff_source(
        self,
        current_view: ViewRequest,
        neat_test_space: SpaceResponse,
        neat_client: NeatClient,
        supporting_view2: ViewRequest,
    ) -> None:
        edge_property = cast(SingleEdgeProperty, current_view.properties[EDGE_PROPERTY_ID])
        new_edge_property = edge_property.model_copy(deep=True, update={"source": supporting_view2.as_reference()})
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, EDGE_PROPERTY_ID: new_edge_property}}
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{EDGE_PROPERTY_ID}.source",
        )

    def test_diff_type(
        self, current_view: ViewRequest, neat_test_space: SpaceResponse, neat_client: NeatClient
    ) -> None:
        edge_property = cast(SingleEdgeProperty, current_view.properties[EDGE_PROPERTY_ID])
        new_edge_property = edge_property.model_copy(
            deep=True,
            update={"type": NodeReference(space=neat_test_space.space, external_id="DifferentNodeType")},
        )
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, EDGE_PROPERTY_ID: new_edge_property}}
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{EDGE_PROPERTY_ID}.type",
        )

    def test_diff_edge_source(
        self,
        current_view: ViewRequest,
        supporting_view: ViewRequest,
        neat_client: NeatClient,
        supporting_edge_view2: ViewRequest,
    ) -> None:
        edge_property = cast(SingleEdgeProperty, current_view.properties[EDGE_PROPERTY_ID])
        new_edge_property = edge_property.model_copy(
            deep=True, update={"edge_source": supporting_edge_view2.as_reference()}
        )
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, EDGE_PROPERTY_ID: new_edge_property}}
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{EDGE_PROPERTY_ID}.edgeSource",
            neat_override_breaking_changes=True,
        )

    def test_diff_direction(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        edge_property = cast(SingleEdgeProperty, current_view.properties[EDGE_PROPERTY_ID])
        new_edge_property = edge_property.model_copy(deep=True, update={"direction": "inwards"})
        new_view = current_view.model_copy(
            update={"properties": {**current_view.properties, EDGE_PROPERTY_ID: new_edge_property}}
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{EDGE_PROPERTY_ID}.direction",
            neat_override_breaking_changes=True,
        )


class TestViewReverseDirectRelationPropertyDiffer:
    def test_diff_type(self, current_view: ViewRequest, neat_client: NeatClient) -> None:
        reverse_property = cast(
            SingleReverseDirectRelationPropertyRequest, current_view.properties[REVERSE_DIRECT_RELATION_PROPERTY_ID]
        )
        # Change from single reverse direct relation to multi reverse direct relation
        new_multi_reverse_property = MultiReverseDirectRelationPropertyRequest.model_validate(
            reverse_property.model_dump(by_alias=True, exclude={"connection_type"})
        )
        new_view = current_view.model_copy(
            update={
                "properties": {
                    **current_view.properties,
                    REVERSE_DIRECT_RELATION_PROPERTY_ID: new_multi_reverse_property,
                }
            }
        )
        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{REVERSE_DIRECT_RELATION_PROPERTY_ID}.connectionType",
            in_error_message="'reverseDirectRelationProperty' would change type from single_reverse_direct_relation to "
            "multi_reverse_direct_relation",
        )

    def test_diff_source(
        self, current_view: ViewRequest, neat_client: NeatClient, supporting_view2: ViewRequest
    ) -> None:
        reverse_property = cast(
            SingleReverseDirectRelationPropertyRequest, current_view.properties[REVERSE_DIRECT_RELATION_PROPERTY_ID]
        )
        new_reverse_property = reverse_property.model_copy(
            deep=True,
            update={"source": supporting_view2.as_reference()},
        )
        new_view = current_view.model_copy(
            update={
                "properties": {**current_view.properties, REVERSE_DIRECT_RELATION_PROPERTY_ID: new_reverse_property}
            }
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{REVERSE_DIRECT_RELATION_PROPERTY_ID}.source",
        )

    def test_diff_through(
        self,
        current_view: ViewRequest,
        supporting_view: ViewRequest,
        neat_client: NeatClient,
        supporting_view2: ViewRequest,
    ) -> None:
        reverse_property = cast(
            SingleReverseDirectRelationPropertyRequest, current_view.properties[REVERSE_DIRECT_RELATION_PROPERTY_ID]
        )
        new_reverse_property = reverse_property.model_copy(
            deep=True,
            update={"through": ViewDirectReference(source=supporting_view2.as_reference(), identifier="directProp")},
        )
        new_view = current_view.model_copy(
            update={
                "properties": {**current_view.properties, REVERSE_DIRECT_RELATION_PROPERTY_ID: new_reverse_property}
            }
        )

        assert_change(
            ViewDiffer({}, {}),
            current_view,
            new_view,
            neat_client.views,
            field_path=f"properties.{REVERSE_DIRECT_RELATION_PROPERTY_ID}.through",
        )
