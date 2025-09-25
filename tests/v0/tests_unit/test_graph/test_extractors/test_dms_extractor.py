from collections import defaultdict
from collections.abc import Iterable
from typing import cast
from unittest.mock import MagicMock

import rdflib
from cognite.client import data_modeling as dm
from cognite.client.data_classes.aggregations import AggregatedNumberedValue
from cognite.client.data_classes.data_modeling.instances import Instance, Properties
from requests import Response

from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._instances.extractors import DMSExtractor
from tests.v0.data import GraphData


class TestDMSExtractor:
    def test_extract_instances(self) -> None:
        total_instances_pair_by_view: dict[dm.ViewId, tuple[int | None, list[Instance]]] = defaultdict(lambda: (0, []))
        for instance in instance_apply_to_read(GraphData.car.INSTANCES):
            if isinstance(instance, dm.Node):
                view_id = next(iter(instance.properties.keys()))
            else:
                # Hardcoded for this test - all edges belong to this view
                view_id = dm.ViewId("sp_example_car", "Car", "v1")
            total_instances, instances = total_instances_pair_by_view[view_id]
            instances.append(instance)
            total_instances_pair_by_view[view_id] = total_instances + 1, instances

        extractor = DMSExtractor(total_instances_pair_by_view)
        expected_triples = set(GraphData.car.TRIPLES)

        triples = set(extractor.extract())

        missing_triples = expected_triples - triples
        assert len(missing_triples) == 0
        extra_triples = triples - expected_triples
        assert len(extra_triples) == 0

    def test_extract_instances_enforce_type(self) -> None:
        view = dm.View(
            space="cdf_cdm",
            external_id="CogniteTimeSeries",
            version="v1",
            properties={},
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            is_global=True,
            last_updated_time=1,
            created_time=1,
            description=None,
            name=None,
        )
        node_a = dm.Node(
            space="my_space",
            external_id="node1",
            version=1,
            type=dm.DirectRelationReference("other_space", "typeA"),
            properties=Properties({view.as_id(): {"isStep": False, "type": "numeric"}}),
            created_time=1,
            last_updated_time=1,
            deleted_time=None,
        )
        node_b = dm.Node(
            space="my_space",
            external_id="node2",
            version=1,
            type=dm.DirectRelationReference("other_space", "typeB"),
            properties=Properties({view.as_id(): {"isStep": False, "type": "numeric"}}),
            last_updated_time=1,
            created_time=1,
            deleted_time=1,
        )
        with monkeypatch_neat_client() as client:
            response = MagicMock(spec=Response)
            response.json.return_value = {
                "items": [item.dump() for item in [node_a, node_b]],
                "nextCursor": None,
            }
            client.post.return_value = response
            client.data_modeling.instances.aggregate.return_value = AggregatedNumberedValue("externalId", 2)
            extractor = DMSExtractor.from_views(client, [view])

            triples = set(extractor.extract())
        type_count = len({triple[2] for triple in triples if triple[1] == rdflib.RDF.type})
        assert type_count == 1


def instance_apply_to_read(instances: Iterable[dm.NodeApply | dm.EdgeApply]) -> Iterable[Instance]:
    for instance in instances:
        if isinstance(instance, dm.NodeApply):
            yield dm.Node(
                space=instance.space,
                external_id=instance.external_id,
                type=instance.type,
                last_updated_time=0,
                created_time=0,
                version=instance.existing_version,
                deleted_time=None,
                properties={cast(dm.ViewId, source.source): source.properties for source in instance.sources or []},
            )
        elif isinstance(instance, dm.EdgeApply):
            yield dm.Edge(
                space=instance.space,
                external_id=instance.external_id,
                type=instance.type,
                start_node=instance.start_node,
                end_node=instance.end_node,
                last_updated_time=0,
                created_time=0,
                version=instance.existing_version,
                deleted_time=None,
                properties={cast(dm.ViewId, source.source): source.properties for source in instance.sources or []},
            )
        else:
            raise NotImplementedError(f'Unknown instance type "{type(instance)}"')
