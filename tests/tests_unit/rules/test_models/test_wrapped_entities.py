from typing import Any

import pytest

from cognite.neat.rules.models.entities import ContainerEntity, DMSNodeEntity
from cognite.neat.rules.models.wrapped_entities import HasDataFilter, NodeTypeFilter, WrappedEntity


class TestWrappedEntities:
    @pytest.mark.parametrize(
        "cls_, raw, expected",
        [
            (
                NodeTypeFilter,
                "NodeType(subject:person)",
                NodeTypeFilter(inner=DMSNodeEntity(space="subject", externalId="person")),
            ),
            (
                HasDataFilter,
                "HasData(subject:person)",
                HasDataFilter(inner=[ContainerEntity(space="subject", externalId="person")]),
            ),
            (NodeTypeFilter, "nodeType", NodeTypeFilter()),
            (HasDataFilter, "hasData", HasDataFilter()),
            (
                HasDataFilter,
                "hasData(space:container1, space:container2)",
                HasDataFilter(
                    inner=[
                        ContainerEntity(space="space", externalId="container1"),
                        ContainerEntity(space="space", externalId="container2"),
                    ]
                ),
            ),
        ],
    )
    def test_load(self, cls_: type[WrappedEntity], raw: Any, expected: WrappedEntity) -> None:
        loaded = cls_.load(raw)

        assert loaded == expected
