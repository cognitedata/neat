from collections.abc import Iterable

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
            raise ValueError("NodeApply is not supported")
        elif isinstance(instance, dm.EdgeApply):
            raise ValueError("EdgeApply is not supported")
        else:
            raise NotImplementedError(f'Unknown instance type "{type(instance)}"')
