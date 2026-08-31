from datetime import datetime, timezone

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms import DataModelRequest, ViewReference, ViewRequest
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.models.dms._view_property import ViewCorePropertyRequest
from cognite.neat._data_model.rules.dms._connections import ConnectionValueTypeUnexisting
from cognite.neat._data_model.rules.dms._views import DataModelViewDoesNotExist


class TestExternalViewReferences:
    def _resources(
        self,
        *,
        dm_version: str = "1.0.0",
        dm_views: list[ViewReference],
        local_views: dict[ViewReference, ViewRequest] | None = None,
    ) -> ValidationResources:
        data_model = DataModelRequest(
            space="sp_ent_ops",
            externalId="dm_ent_emergency360",
            version=dm_version,
            views=dm_views,
        )
        dm_ref = data_model.as_reference()
        local = SchemaSnapshot(
            timestamp=datetime.now(timezone.utc),
            data_model={dm_ref: data_model},
            views=local_views or {},
        )
        return ValidationResources(
            modus_operandi="additive",
            local=local,
            cdf=SchemaSnapshot(),
            limits=SchemaLimits(),
        )

    def test_cross_version_data_model_view_does_not_require_local_definition(self) -> None:
        own_view = ViewReference(space="sp_ent_ops", external_id="E360Person", version="1.0.0")
        tag_view = ViewReference(space="sp_ent_ops", external_id="Tag", version="1.18.1")
        resources = self._resources(
            dm_views=[own_view, tag_view],
            local_views={
                own_view: ViewRequest(
                    space="sp_ent_ops",
                    externalId="E360Person",
                    version="1.0.0",
                    properties={},
                )
            },
        )

        issues = DataModelViewDoesNotExist(resources).validate()

        assert issues == []

    def test_same_version_data_model_view_still_requires_local_definition(self) -> None:
        missing_view = ViewReference(space="sp_ent_ops", external_id="E360Person", version="1.0.0")
        resources = self._resources(dm_views=[missing_view])

        issues = DataModelViewDoesNotExist(resources).validate()

        assert len(issues) == 1
        assert "E360Person" in issues[0].message

    def test_cross_version_connection_target_does_not_require_local_definition(self) -> None:
        own_view = ViewReference(space="sp_ent_ops", external_id="E360Exercise", version="1.0.0")
        tag_view = ViewReference(space="sp_ent_ops", external_id="Tag", version="1.18.1")
        container = ContainerReference(space="sp_ent_ops", external_id="E360Exercise")
        resources = self._resources(
            dm_views=[own_view],
            local_views={
                own_view: ViewRequest(
                    space="sp_ent_ops",
                    externalId="E360Exercise",
                    version="1.0.0",
                    properties={
                        "assets": ViewCorePropertyRequest(
                            container=container,
                            containerPropertyIdentifier="assets",
                            source=tag_view,
                        )
                    },
                )
            },
        )

        issues = ConnectionValueTypeUnexisting(resources).validate()

        assert issues == []
