from collections.abc import Iterable

import pytest
from cognite.client import data_modeling as dm
from rdflib import RDF, Literal, Namespace

from cognite.neat import NeatSession
from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._constants import DEFAULT_SPACE_URI
from cognite.neat.core._instances.extractors import BaseExtractor
from cognite.neat.core._shared import Triple


@pytest.fixture()
def session_with_model() -> NeatSession:
    with monkeypatch_neat_client() as client:
        space = dm.Space(
            "my_space",
            False,
            1,
            1,
        )
        view = dm.View(
            space=space.space,
            external_id="Asset",
            version="v1",
            name=None,
            description=None,
            created_time=1234567890,
            last_updated_time=1234567890,
            filter=None,
            implements=None,
            writable=True,
            is_global=False,
            used_for="node",
            properties={
                "name": dm.MappedProperty(
                    container=dm.ContainerId("my_space", "my_container"),
                    container_property_identifier="name",
                    type=dm.data_types.Text(),
                    auto_increment=False,
                    nullable=True,
                    immutable=False,
                ),
                "parent": dm.MappedProperty(
                    container=dm.ContainerId("my_space", "my_container"),
                    container_property_identifier="parent",
                    type=dm.data_types.DirectRelation(is_list=False),
                    auto_increment=False,
                    nullable=True,
                    immutable=False,
                ),
            },
        )
        client.data_modeling.data_models.retrieve.return_value = dm.DataModelList(
            [
                dm.DataModel(
                    space="my_space",
                    external_id="my_model",
                    version="v1",
                    created_time=1234567890,
                    last_updated_time=1234567890,
                    is_global=False,
                    name=None,
                    description=None,
                    views=[view],
                )
            ]
        )
        client.data_modeling.containers.retrieve.return_value = dm.ContainerList(
            [
                dm.Container(
                    space="my_space",
                    external_id="my_container",
                    name=None,
                    description=None,
                    created_time=1234567890,
                    last_updated_time=1234567890,
                    is_global=False,
                    used_for="node",
                    constraints=None,
                    indexes=None,
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
        )
        client.data_modeling.spaces.retrieve.return_value = dm.SpaceList([space])
        client.data_modeling.views.retrieve.return_value = dm.ViewList([view])
        neat = NeatSession(client=client)
    return neat


class TestConnectData:
    def test_connect_data_to_existing_model(self, session_with_model: NeatSession) -> None:
        neat = session_with_model
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
        neat.read.cdf.data_model(("my_space", "my_model", "v1"))
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
