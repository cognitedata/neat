from typing import Any

import pytest
from cognite.client.data_classes.data_modeling import ContainerId, DataModelId, ViewId

from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DataModelEntity,
    DMSEntity,
    Entity,
    ViewPropertyEntity,
    Undefined,
    Unknown,
    ViewEntity,
)


class TestEntities:
    @pytest.mark.parametrize(
        "cls_, raw, expected",
        [
            (ClassEntity, "subject:person", ClassEntity(prefix="subject", suffix="person")),
            (ViewEntity, "subject:person(version=1.0)", ViewEntity(prefix="subject", suffix="person", version="1.0")),
            (Entity, "#N/A", Entity(prefix=Undefined, suffix=Unknown)),
            (ViewEntity, "Person", ViewEntity(prefix=Undefined, suffix="Person", version=None)),
            (ViewEntity, "Person(version=3)", ViewEntity(prefix=Undefined, suffix="Person", version="3")),
            (
                    ViewPropertyEntity,
                "Person(property=name)",
                    ViewPropertyEntity(prefix=Undefined, suffix="Person", version=None, property="name"),
            ),
            (
                    ViewPropertyEntity,
                "Person(property=name, version=1)",
                    ViewPropertyEntity(prefix=Undefined, suffix="Person", version="1", property="name"),
            ),
            (
                    ViewPropertyEntity,
                "Person(property=name,version=1)",
                    ViewPropertyEntity(prefix=Undefined, suffix="Person", version="1", property="name"),
            ),
            (
                    ViewPropertyEntity,
                "sp_my_space:Person(property=name,version=1)",
                    ViewPropertyEntity(prefix="sp_my_space", suffix="Person", version="1", property="name"),
            ),
            (
                    ViewPropertyEntity,
                "sp_my_space:Person(version=1, property=name)",
                    ViewPropertyEntity(prefix="sp_my_space", suffix="Person", version="1", property="name"),
            ),
        ],
    )
    def test_load(self, cls_: type[Entity], raw: Any, expected: Entity) -> None:
        loaded = cls_.load(raw)

        assert loaded == expected

    @pytest.mark.parametrize(
        "entity, default_space, expected_id",
        [
            (ContainerEntity.load("Person"), "sp_default_space", ContainerId("sp_default_space", "Person")),
            (ViewEntity.load("Person(version=1.0)"), "sp_default_space", ViewId("sp_default_space", "Person", "1.0")),
            (
                DataModelEntity.load("my_space:my_model(version=1)"),
                "sp_default_space",
                DataModelId("my_space", "my_model", "1"),
            ),
        ],
    )
    def test_default_space(self, entity: DMSEntity, default_space: str, expected_id: Any):
        DMSEntity.set_default_space(default_space)

        assert entity.as_id() == expected_id
