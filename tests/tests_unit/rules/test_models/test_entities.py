from typing import Any

import pytest

from cognite.neat.rules.models.entities import (
    ClassEntity,
    Entity,
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
        ],
    )
    def test_load(self, cls_: type[Entity], raw: Any, expected: Entity) -> None:
        loaded = cls_.load(raw, space=DEFAULT_SPACE, version=DEFAULT_VERSION)

        assert loaded == expected
