from typing import Any

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.rules.models.entities import ContainerEntity, DMSNodeEntity
from cognite.neat.rules.models.wrapped_entities import DMSFilter, HasDataFilter, NodeTypeFilter, WrappedEntity


class TestWrappedEntities:
    @pytest.mark.parametrize(
        "cls_, raw, expected",
        [
            (
                NodeTypeFilter,
                "NodeType(subject:person)",
                NodeTypeFilter(inner=[DMSNodeEntity(space="subject", externalId="person")]),
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
            (
                NodeTypeFilter,
                "nodeType(space:node1, space:node2)",
                NodeTypeFilter(
                    inner=[
                        DMSNodeEntity(space="space", externalId="node1"),
                        DMSNodeEntity(space="space", externalId="node2"),
                    ]
                ),
            ),
        ],
    )
    def test_load(self, cls_: type[WrappedEntity], raw: Any, expected: WrappedEntity) -> None:
        loaded = cls_.load(raw)

        assert loaded == expected
        assert repr(loaded) == repr(expected)
        assert str(loaded) == str(expected)

    @pytest.mark.parametrize(
        "filter_, expected",
        [
            (
                dm.filters.HasData(containers=[dm.ContainerId(space="space", external_id="container1")]),
                HasDataFilter(inner=[ContainerEntity(space="space", externalId="container1")]),
            ),
            (
                dm.filters.Equals(["node", "type"], {"space": "space", "externalId": "node1"}),
                NodeTypeFilter(inner=[DMSNodeEntity(space="space", externalId="node1")]),
            ),
            (
                dm.filters.In(
                    ["node", "type"],
                    [{"space": "space", "externalId": "node1"}, {"space": "space", "externalId": "node2"}],
                ),
                NodeTypeFilter(
                    inner=[
                        DMSNodeEntity(space="space", externalId="node1"),
                        DMSNodeEntity(space="space", externalId="node2"),
                    ]
                ),
            ),
        ],
    )
    def test_from_dms_filter(self, filter_: dm.Filter, expected: DMSFilter) -> None:
        loaded = DMSFilter.from_dms_filter(filter_)

        assert loaded == expected
