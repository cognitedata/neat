from collections.abc import Iterable, Sequence
from typing import Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes import Source
from cognite.client.data_classes.data_modeling.instances import Instance

from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._graph.extractors import DMSGraphExtractor
from tests.data import car
from tests.utils import as_read_containers, as_read_instance, as_read_space


def car_instances(
    instance_type: Literal["node", "edge"] = "node", sources: Source | Sequence[Source] | None = None, **other_args
) -> Iterable[Instance]:
    for instance in car.INSTANCES:
        if instance_type == "node" and isinstance(instance, dm.EdgeApply):
            continue
        if instance_type == "edge" and isinstance(instance, dm.NodeApply):
            continue
        if sources is not None and instance.sources and instance.sources[0].source not in sources:
            continue
        if not instance.sources and "filter" not in other_args:
            # If there is not source, we have an edge type, which should have a filter.
            continue
        yield as_read_instance(instance)


class TestDMSGraphExtractor:
    def test_extract_car_example(self) -> None:
        with monkeypatch_neat_client() as client:
            client.data_modeling.instances.side_effect = car_instances
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList(
                [as_read_space(dm.SpaceApply(car.MODEL_SPACE))]
            )
            client.data_modeling.views.retrieve.return_value = dm.ViewList(car.CAR_MODEL.views)
            client.data_modeling.containers.retrieve.return_value = as_read_containers(car.CONTAINERS)
            extractor = DMSGraphExtractor(car.CAR_MODEL, client)

            triples = set(extractor.extract())
            info_rules = extractor.get_information_rules()
            dms_rules = extractor.get_dms_rules()

        expected_info = car.get_care_rules()
        assert triples == set(car.TRIPLES)
        assert {cls_.class_.suffix for cls_ in info_rules.classes} == {
            cls_.class_.suffix for cls_ in expected_info.classes
        }
        assert {view.view.external_id for view in dms_rules.views} == {view.external_id for view in car.CAR_MODEL.views}
