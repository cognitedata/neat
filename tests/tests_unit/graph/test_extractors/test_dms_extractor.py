from collections.abc import Iterable
from typing import cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import InstanceApply
from cognite.client.data_classes.data_modeling.instances import Instance

from cognite.neat.graph.extractors import DMSExtractor
from tests.data import car


class TestDMSExtractor:
    def test_extract_instances(self) -> None:
        extractor = DMSExtractor(instance_apply_to_read(car.INSTANCES))

        triples = list(extractor.extract())

        assert len(triples) == len(car.TRIPLES)


def instance_apply_to_read(instances: Iterable[InstanceApply]) -> Iterable[Instance]:
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