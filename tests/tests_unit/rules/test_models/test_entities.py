from typing import Any

import pytest

from cognite.neat.rules.models.entities import Entity, ViewEntity, ViewNonVersionedEntity


class TestEntities:
    @pytest.mark.parametrize(
        "cls_, raw",
        [
            (Entity, "subject:person"),
            (ViewNonVersionedEntity, "subject:person"),
            (ViewEntity, "subject:person(version=1.0)"),
        ],
    )
    def test_load_dump(self, cls_: type[Entity], raw: Any) -> None:
        loaded = cls_.load(raw)

        assert loaded.dump() == str(raw)
