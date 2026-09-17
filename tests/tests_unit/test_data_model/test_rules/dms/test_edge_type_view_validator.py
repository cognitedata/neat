from datetime import datetime, timezone

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    NodeReference,
    TextProperty,
    ViewReference,
    ViewRequest,
)
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._view_property import (
    MultiEdgeProperty,
    ViewCorePropertyRequest,
)
from cognite.neat._data_model.rules.dms._views import EdgeTypeViewHasConnectionProperty

SPACE = "sp_ent_ops"
VERSION = "1.0.0"


class TestEdgeTypeViewHasConnectionProperty:
    def _resources(
        self,
        *,
        containers: dict[ContainerReference, ContainerRequest],
        views: dict[ViewReference, ViewRequest],
    ) -> ValidationResources:
        data_model = DataModelRequest(
            space=SPACE,
            externalId="dm_test",
            version=VERSION,
            views=list(views.keys()),
        )
        local = SchemaSnapshot(
            timestamp=datetime.now(timezone.utc),
            data_model={data_model.as_reference(): data_model},
            containers=containers,
            views=views,
        )
        return ValidationResources(
            modus_operandi="additive",
            local=local,
            cdf=SchemaSnapshot(),
            limits=SchemaLimits(),
        )

    def _edge_container(self, external_id: str) -> ContainerRequest:
        return ContainerRequest(
            space=SPACE,
            externalId=external_id,
            usedFor="edge",
            properties={
                "fact": ContainerPropertyDefinition(type=TextProperty()),
            },
        )

    def _node_container(self, external_id: str) -> ContainerRequest:
        return ContainerRequest(
            space=SPACE,
            externalId=external_id,
            usedFor="node",
            properties={
                "name": ContainerPropertyDefinition(type=TextProperty()),
            },
        )

    def _all_container(self, external_id: str) -> ContainerRequest:
        return ContainerRequest(
            space=SPACE,
            externalId=external_id,
            usedFor="all",
            properties={
                "shared": ContainerPropertyDefinition(type=TextProperty()),
            },
        )

    def test_edge_link_view_without_connections_is_valid(self) -> None:
        edge_container = self._edge_container("Participation")
        edge_view = ViewReference(space=SPACE, external_id="Participation", version=VERSION)
        resources = self._resources(
            containers={edge_container.as_reference(): edge_container},
            views={
                edge_view: ViewRequest(
                    space=SPACE,
                    externalId="Participation",
                    version=VERSION,
                    properties={
                        "fact": ViewCorePropertyRequest(
                            container=edge_container.as_reference(),
                            containerPropertyIdentifier="fact",
                        )
                    },
                )
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert issues == []

    def test_edge_link_view_with_edge_connection_is_invalid(self) -> None:
        edge_container = self._edge_container("Participation")
        person_container = self._node_container("Person")
        edge_view = ViewReference(space=SPACE, external_id="Participation", version=VERSION)
        person_view = ViewReference(space=SPACE, external_id="Person", version=VERSION)
        resources = self._resources(
            containers={
                edge_container.as_reference(): edge_container,
                person_container.as_reference(): person_container,
            },
            views={
                edge_view: ViewRequest(
                    space=SPACE,
                    externalId="Participation",
                    version=VERSION,
                    properties={
                        "fact": ViewCorePropertyRequest(
                            container=edge_container.as_reference(),
                            containerPropertyIdentifier="fact",
                        ),
                        "attendances": MultiEdgeProperty(
                            source=person_view,
                            type=NodeReference(space=SPACE, external_id="Participation.attendances"),
                            edge_source=edge_view,
                        ),
                    },
                ),
                person_view: ViewRequest(
                    space=SPACE,
                    externalId="Person",
                    version=VERSION,
                    properties={},
                ),
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert len(issues) == 1
        assert issues[0].code == "NEAT-DMS-VIEW-005"
        assert "attendances" in issues[0].message
        assert "multi_edge_connection" in issues[0].message

    def test_node_view_with_edge_connection_is_allowed(self) -> None:
        edge_container = self._edge_container("Participation")
        person_container = self._node_container("Person")
        edge_view = ViewReference(space=SPACE, external_id="Participation", version=VERSION)
        person_view = ViewReference(space=SPACE, external_id="Person", version=VERSION)
        resources = self._resources(
            containers={
                edge_container.as_reference(): edge_container,
                person_container.as_reference(): person_container,
            },
            views={
                edge_view: ViewRequest(
                    space=SPACE,
                    externalId="Participation",
                    version=VERSION,
                    properties={
                        "fact": ViewCorePropertyRequest(
                            container=edge_container.as_reference(),
                            containerPropertyIdentifier="fact",
                        )
                    },
                ),
                person_view: ViewRequest(
                    space=SPACE,
                    externalId="Person",
                    version=VERSION,
                    properties={
                        "name": ViewCorePropertyRequest(
                            container=person_container.as_reference(),
                            containerPropertyIdentifier="name",
                        ),
                        "attendances": MultiEdgeProperty(
                            source=person_view,
                            type=NodeReference(space=SPACE, external_id="Person.attendances"),
                            edge_source=edge_view,
                        ),
                    },
                ),
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert issues == []

    def test_view_with_edge_and_node_containers_flags_edge_connections(self) -> None:
        edge_container = self._edge_container("Participation")
        person_container = self._node_container("Person")
        edge_view = ViewReference(space=SPACE, external_id="Participation", version=VERSION)
        person_view = ViewReference(space=SPACE, external_id="Person", version=VERSION)
        resources = self._resources(
            containers={
                edge_container.as_reference(): edge_container,
                person_container.as_reference(): person_container,
            },
            views={
                edge_view: ViewRequest(
                    space=SPACE,
                    externalId="Participation",
                    version=VERSION,
                    properties={
                        "fact": ViewCorePropertyRequest(
                            container=edge_container.as_reference(),
                            containerPropertyIdentifier="fact",
                        ),
                        "name": ViewCorePropertyRequest(
                            container=person_container.as_reference(),
                            containerPropertyIdentifier="name",
                        ),
                        "attendances": MultiEdgeProperty(
                            source=person_view,
                            type=NodeReference(space=SPACE, external_id="Participation.attendances"),
                            edge_source=edge_view,
                        ),
                    },
                ),
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert len(issues) == 1
        assert issues[0].code == "NEAT-DMS-VIEW-005"

    def test_view_with_edge_and_all_containers_flags_edge_connections(self) -> None:
        edge_container = self._edge_container("Participation")
        shared_container = self._all_container("SharedFacts")
        edge_view = ViewReference(space=SPACE, external_id="Participation", version=VERSION)
        person_view = ViewReference(space=SPACE, external_id="Person", version=VERSION)
        resources = self._resources(
            containers={
                edge_container.as_reference(): edge_container,
                shared_container.as_reference(): shared_container,
            },
            views={
                edge_view: ViewRequest(
                    space=SPACE,
                    externalId="Participation",
                    version=VERSION,
                    properties={
                        "fact": ViewCorePropertyRequest(
                            container=edge_container.as_reference(),
                            containerPropertyIdentifier="fact",
                        ),
                        "shared": ViewCorePropertyRequest(
                            container=shared_container.as_reference(),
                            containerPropertyIdentifier="shared",
                        ),
                        "attendances": MultiEdgeProperty(
                            source=person_view,
                            type=NodeReference(space=SPACE, external_id="Participation.attendances"),
                            edge_source=edge_view,
                        ),
                    },
                ),
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert len(issues) == 1
        assert issues[0].code == "NEAT-DMS-VIEW-005"

    def test_view_with_only_all_container_allows_edge_connections(self) -> None:
        shared_container = self._all_container("SharedFacts")
        node_view = ViewReference(space=SPACE, external_id="NodeView", version=VERSION)
        resources = self._resources(
            containers={shared_container.as_reference(): shared_container},
            views={
                node_view: ViewRequest(
                    space=SPACE,
                    externalId="NodeView",
                    version=VERSION,
                    properties={
                        "shared": ViewCorePropertyRequest(
                            container=shared_container.as_reference(),
                            containerPropertyIdentifier="shared",
                        ),
                        "related": MultiEdgeProperty(
                            source=node_view,
                            type=NodeReference(space=SPACE, external_id="NodeView.related"),
                        ),
                    },
                ),
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert issues == []

    def test_view_with_unknown_container_is_not_classified_as_edge_type(self) -> None:
        edge_view = ViewReference(space=SPACE, external_id="Participation", version=VERSION)
        person_view = ViewReference(space=SPACE, external_id="Person", version=VERSION)
        missing_container = ContainerReference(space=SPACE, external_id="MissingEdgeContainer")
        resources = self._resources(
            containers={},
            views={
                edge_view: ViewRequest(
                    space=SPACE,
                    externalId="Participation",
                    version=VERSION,
                    properties={
                        "fact": ViewCorePropertyRequest(
                            container=missing_container,
                            containerPropertyIdentifier="fact",
                        ),
                        "attendances": MultiEdgeProperty(
                            source=person_view,
                            type=NodeReference(space=SPACE, external_id="Participation.attendances"),
                            edge_source=edge_view,
                        ),
                    },
                ),
            },
        )

        issues = EdgeTypeViewHasConnectionProperty(resources).validate()

        assert issues == []
