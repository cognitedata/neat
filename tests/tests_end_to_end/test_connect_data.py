from collections.abc import Iterable

from cognite.client import data_modeling as dm
from rdflib import RDF, Literal, Namespace

from cognite.neat import NeatSession
from cognite.neat.core._client.data_classes.data_modeling import ContainerApplyDict, SpaceApplyDict, ViewApplyDict
from cognite.neat.core._client.data_classes.schema import DMSSchema
from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._instances.extractors import BaseExtractor
from cognite.neat.core._shared import Triple


def create_session_with_model(schema: DMSSchema) -> NeatSession:
    with monkeypatch_neat_client() as client:
        read_model = schema.as_read_model()
        read_spaces = schema.as_read_spaces()
        read_containers = schema.as_read_containers()
        client.data_modeling.data_models.retrieve.return_value = dm.DataModelList([read_model])
        client.data_modeling.containers.retrieve.return_value = dm.ContainerList(read_containers)
        client.data_modeling.spaces.retrieve.return_value = read_spaces
        client.data_modeling.views.retrieve.return_value = dm.ViewList(read_model.views)
        neat = NeatSession(client=client)
    return neat


class TestConnectData:
    def test_connect_data_to_existing_model(self) -> None:
        neat = create_session_with_model(ASSET_MODEL)
        view_id = dm.ViewId("my_space", "Asset", "v1")

        instance_space = Namespace(DEFAULT_SPACE_URI.format(space="sp_instances"))
        schema_space = Namespace(DEFAULT_SPACE_URI.format(space="my_space"))

        class SomeTriples(BaseExtractor):
            def extract(self) -> Iterable[Triple]:
                my_thing = instance_space["my_thing"]
                yield my_thing, RDF.type, schema_space["Asset"]
                yield my_thing, schema_space["name"], Literal("My Thing")
                my_other_thing = instance_space["my_other_thing"]
                yield my_other_thing, RDF.type, schema_space["Asset"]
                yield my_other_thing, schema_space["name"], Literal("My Other Thing")

        neat._state.instances.store.write(SomeTriples())
        neat.read.cdf.data_model(("my_space", "asset_model", "v1"))
        neat.connect_data()

        instances, issues = neat.to._python.instances(use_source_space=True)

        assert len(issues) == 0
        assert len(instances) == 2
        expected = dm.NodeApplyList(
            [
                dm.NodeApply(
                    "sp_instances",
                    "my_other_thing",
                    sources=[
                        dm.NodeOrEdgeData(view_id, {"name": "My Other Thing"}),
                    ],
                    type=dm.DirectRelationReference("my_space", "Asset"),
                ),
                dm.NodeApply(
                    "sp_instances",
                    "my_thing",
                    sources=[
                        dm.NodeOrEdgeData(view_id, {"name": "My Thing"}),
                    ],
                    type=dm.DirectRelationReference("my_space", "Asset"),
                ),
            ]
        )
        assert [node.dump() for node in instances] == expected.dump()

    def test_connect_data_to_existing_with_mapping(self) -> None:
        neat = create_session_with_model(ASSET_EQUIPMENT_MODEL)
        asset_id = dm.ViewId("my_space", "Asset", "v1")
        heat_exchanger_id = dm.ViewId("my_space", "HeatExchanger", "v1")
        pump_id = dm.ViewId("my_space", "Pump", "v1")

        instance_space = Namespace(DEFAULT_SPACE_URI.format(space="sp_instances"))
        schema_space = Namespace(DEFAULT_SPACE_URI.format(space="my_space"))

        class SomeTriples(BaseExtractor):
            def extract(self) -> Iterable[Triple]:
                root = instance_space["root"]
                name = schema_space["name"]
                parent = schema_space["parent"]
                asset_type = schema_space["Asset"]
                yield root, RDF.type, asset_type
                yield root, name, Literal("Root Asset")
                heat_exchanger = instance_space["heat_exchanger"]
                pump = instance_space["pump"]
                yield heat_exchanger, RDF.type, asset_type
                yield heat_exchanger, name, Literal("Heat Exchanger")
                yield heat_exchanger, parent, root
                yield pump, RDF.type, asset_type
                yield pump, name, Literal("Pump")
                yield pump, parent, root

        neat._state.instances.store.write(SomeTriples())
        neat.set.instances.type_by_id(
            {"sp_instances:heat_exchanger": heat_exchanger_id.external_id, "sp_instances:pump": pump_id.external_id},
            space="sp_instances",
        )

        neat.read.cdf.data_model(ASSET_EQUIPMENT_MODEL.data_model.as_id())

        neat.connect_data(
            {("HeatExchanger", "parent"): ("HeatExchanger", "asset"), ("Pump", "parent"): ("Pump", "asset")}
        )

        instances, issues = neat.to._python.instances(use_source_space=True)

        assert len(issues) == 0
        assert len(instances) == 3
        expected = dm.NodeApplyList(
            [
                dm.NodeApply(
                    "sp_instances",
                    "root",
                    sources=[
                        dm.NodeOrEdgeData(asset_id, {"name": "Root Asset"}),
                    ],
                    type=dm.DirectRelationReference("my_space", "Asset"),
                ),
                dm.NodeApply(
                    "sp_instances",
                    "heat_exchanger",
                    sources=[
                        dm.NodeOrEdgeData(
                            heat_exchanger_id,
                            {"name": "Heat Exchanger", "asset": {"space": "sp_instances", "externalId": "root"}},
                        ),
                    ],
                    type=dm.DirectRelationReference("my_space", "HeatExchanger"),
                ),
                dm.NodeApply(
                    "sp_instances",
                    "pump",
                    sources=[
                        dm.NodeOrEdgeData(
                            pump_id, {"name": "Pump", "asset": {"space": "sp_instances", "externalId": "root"}}
                        ),
                    ],
                    type=dm.DirectRelationReference("my_space", "Pump"),
                ),
            ]
        )
        assert [node.dump() for node in instances] == expected.dump()


_space = "my_space"
ASSET_MODEL = DMSSchema(
    data_model=dm.DataModelApply(
        space=_space, external_id="asset_model", version="v1", views=[dm.ViewId(_space, "Asset", "v1")]
    ),
    spaces=SpaceApplyDict([dm.SpaceApply(_space)]),
    views=ViewApplyDict(
        [
            dm.ViewApply(
                space=_space,
                external_id="Asset",
                version="v1",
                properties={
                    "name": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="name",
                    ),
                    "parent": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="parent",
                    ),
                },
            )
        ]
    ),
    containers=ContainerApplyDict(
        [
            dm.ContainerApply(
                space=_space,
                external_id="my_container",
                properties={
                    "name": dm.ContainerProperty(
                        type=dm.data_types.Text(),
                        auto_increment=False,
                        nullable=True,
                        immutable=False,
                    ),
                    "parent": dm.ContainerProperty(
                        type=dm.data_types.DirectRelation(is_list=False),
                        auto_increment=False,
                        nullable=True,
                        immutable=False,
                    ),
                },
            )
        ]
    ),
)
ASSET_EQUIPMENT_MODEL = DMSSchema(
    data_model=dm.DataModelApply(
        space=_space,
        external_id="asset_equipment_model_model",
        version="v1",
        views=[
            dm.ViewId(_space, "Asset", "v1"),
            dm.ViewId(_space, "HeatExchanger", "v1"),
            dm.ViewId(_space, "Pump", "v1"),
        ],
    ),
    spaces=SpaceApplyDict([dm.SpaceApply(_space)]),
    views=ViewApplyDict(
        [
            dm.ViewApply(
                space=_space,
                external_id="Asset",
                version="v1",
                properties={
                    "name": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="name",
                    ),
                    "parent": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="parent",
                    ),
                },
            ),
            dm.ViewApply(
                space=_space,
                external_id="HeatExchanger",
                version="v1",
                properties={
                    "name": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="name",
                    ),
                    "asset": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="parent",
                    ),
                },
            ),
            dm.ViewApply(
                space=_space,
                external_id="Pump",
                version="v1",
                properties={
                    "name": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="name",
                    ),
                    "asset": dm.MappedPropertyApply(
                        container=dm.ContainerId(_space, "my_container"),
                        container_property_identifier="parent",
                    ),
                },
            ),
        ]
    ),
    containers=ContainerApplyDict(
        [
            dm.ContainerApply(
                space=_space,
                external_id="my_container",
                properties={
                    "name": dm.ContainerProperty(
                        type=dm.data_types.Text(),
                        auto_increment=False,
                        nullable=True,
                        immutable=False,
                    ),
                    "parent": dm.ContainerProperty(
                        type=dm.data_types.DirectRelation(is_list=False),
                        auto_increment=False,
                        nullable=True,
                        immutable=False,
                    ),
                },
            )
        ]
    ),
)
