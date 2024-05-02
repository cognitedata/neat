from typing import Any

import pytest
from cognite.client.data_classes.data_modeling import DataModelId, PropertyId, ViewId

from cognite.neat.rules.models.entities import (
    ClassEntity,
    DataModelEntity,
    DMSUnknownEntity,
    Entity,
    ReferenceEntity,
    Undefined,
    Unknown,
    ViewEntity,
    ViewPropertyEntity,
)

DEFAULT_SPACE = "sp_my_space"
DEFAULT_VERSION = "vDefault"


class TestEntities:
    @pytest.mark.parametrize(
        "cls_, raw, expected",
        [
            (ClassEntity, "subject:person", ClassEntity(prefix="subject", suffix="person", version=DEFAULT_VERSION)),
            (
                ViewEntity,
                "subject:person(version=1.0)",
                ViewEntity(space="subject", externalId="person", version="1.0"),
            ),
            (Entity, "#N/A", Entity(prefix=Undefined, suffix=Unknown)),
            (ViewEntity, "Person", ViewEntity(space=DEFAULT_SPACE, externalId="Person", version=DEFAULT_VERSION)),
            (ViewEntity, "Person(version=3)", ViewEntity(space=DEFAULT_SPACE, externalId="Person", version="3")),
            (
                ViewPropertyEntity,
                "Person(property=name)",
                ViewPropertyEntity(space=DEFAULT_SPACE, externalId="Person", version=DEFAULT_VERSION, property="name"),
            ),
            (
                ViewPropertyEntity,
                "Person(property=name, version=1)",
                ViewPropertyEntity(space=DEFAULT_SPACE, externalId="Person", version="1", property="name"),
            ),
            (
                ViewPropertyEntity,
                "Person(property=name,version=1)",
                ViewPropertyEntity(space=DEFAULT_SPACE, externalId="Person", version="1", property="name"),
            ),
            (
                ViewPropertyEntity,
                "sp_my_space:Person(property=name,version=1)",
                ViewPropertyEntity(space="sp_my_space", externalId="Person", version="1", property="name"),
            ),
            (
                ViewPropertyEntity,
                "sp_my_space:Person(version=1, property=name)",
                ViewPropertyEntity(space="sp_my_space", externalId="Person", version="1", property="name"),
            ),
            (
                ViewEntity,
                "#N/A",
                DMSUnknownEntity(),
            ),
            (
                ViewPropertyEntity,
                "#N/A",
                DMSUnknownEntity(),
            ),
            (
                ClassEntity,
                "#N/A",
                Entity(prefix=Undefined, suffix=Unknown),
            ),
        ],
    )
    def test_load(self, cls_: type[Entity], raw: Any, expected: Entity) -> None:
        loaded = cls_.load(raw, space=DEFAULT_SPACE, version=DEFAULT_VERSION)

        assert loaded == expected


class TestDataModelEntity:
    @pytest.mark.parametrize(
        "raw, expected, expected_id",
        [
            (
                "test:TestGraphQL1(version=3)",
                DataModelEntity(space="test", externalId="TestGraphQL1", version="3"),
                DataModelId("test", "TestGraphQL1", "3"),
            ),
            (
                "test:TestGraphQL1",
                DataModelEntity(space="test", externalId="TestGraphQL1", version=DEFAULT_VERSION),
                DataModelId("test", "TestGraphQL1", DEFAULT_VERSION),
            ),
        ],
    )
    def test_load(self, raw: str, expected: DataModelEntity, expected_id: DataModelId) -> None:
        actual = DataModelEntity.load(raw, space=DEFAULT_SPACE, version=DEFAULT_VERSION)

        assert actual == expected
        assert actual.as_id() == expected_id


class TestViewPropertyEntity:
    @pytest.mark.parametrize(
        "raw, expected, expected_id",
        [
            pytest.param(
                "test:TestGraphQL1(version=3, property=prop1)",
                ViewPropertyEntity(space="test", externalId="TestGraphQL1", version="3", property="prop1"),
                PropertyId(ViewId("test", "TestGraphQL1", "3"), "prop1"),
                id="Prefix, suffix, version and prop",
            ),
            pytest.param(
                "test:TestGraphQL1(property=prop1)",
                ViewPropertyEntity(space="test", externalId="TestGraphQL1", version=DEFAULT_VERSION, property="prop1"),
                PropertyId(ViewId("test", "TestGraphQL1", DEFAULT_VERSION), "prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
        ],
    )
    def test_load(self, raw: str, expected: ViewPropertyEntity, expected_id: PropertyId) -> None:
        actual = ViewPropertyEntity.load(raw, space=DEFAULT_SPACE, version=DEFAULT_VERSION)

        assert actual == expected
        assert actual.as_id() == expected_id


class TestReferenceType:
    @pytest.mark.parametrize(
        "raw, expected,",
        [
            pytest.param(
                "test:TestGraphQL1(version=3, property=prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version="3", property="prop1"),
                id="Prefix, suffix, version and prop",
            ),
            pytest.param(
                "test:TestGraphQL1(property=prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property="prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "test:TestGraphQL1(property=test:prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property="test:prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "test:TestGraphQL1",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property=None),
                id="Prefix, suffix and prop. Skip version",
            ),
        ],
    )
    def test_load(self, raw: str, expected: ReferenceEntity) -> None:
        actual = ReferenceEntity.load(raw)
        assert actual == expected
