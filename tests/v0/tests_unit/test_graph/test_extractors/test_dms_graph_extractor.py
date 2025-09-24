from collections.abc import Callable, Iterable
from typing import Literal
from unittest.mock import MagicMock

from cognite.client import data_modeling as dm
from cognite.client.data_classes import Source
from cognite.client.data_classes.data_modeling.instances import Instance
from requests import Response

from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._instances.extractors import DMSGraphExtractor
from tests.v0.data import GraphData
from tests.v0.utils import as_read_containers, as_read_instance, as_read_space


def create_car_instance(max_run: int = 1) -> Callable:
    run_count = 0

    # The extractor will call the instance endpoint multiple times. One for nodes,
    # one for edges, and one for edge types.
    # In this mocking function, we return all instances in the first call, and do nothing
    # in the subsequent calls. This is to avoid having extra logic here to split the instances
    # and potentially introduce bugs.
    def car_instances(
        instance_type: Literal["node", "edge"] = "node", source: Source | None = None, **other_args
    ) -> Iterable[Instance]:
        #
        nonlocal run_count
        if run_count >= max_run:
            return
        for instance in GraphData.car.INSTANCES:
            yield as_read_instance(instance)
        run_count += 1

    return car_instances


class TestDMSGraphExtractor:
    def test_extract_car_example(self) -> None:
        car = GraphData.car
        with monkeypatch_neat_client() as client:
            response = MagicMock(spec=Response)
            response.json.return_value = {
                "items": [item.dump() for item in create_car_instance(1)()],
                "nextCursor": None,
            }
            client.post.return_value = response
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList(
                [as_read_space(dm.SpaceApply(car.MODEL_SPACE))]
            )
            client.data_modeling.views.retrieve.return_value = dm.ViewList(car.CAR_MODEL.views)
            client.data_modeling.containers.retrieve.return_value = as_read_containers(car.CONTAINERS)
            extractor = DMSGraphExtractor(car.CAR_MODEL, client)

            triples = set(extractor.extract())
            info_rules = extractor.get_conceptual_data_model()
            dms_rules = extractor.get_physical_data_model()

        expected_info = car.get_care_rules()
        assert triples == set(car.TRIPLES)
        assert {cls_.concept.suffix for cls_ in info_rules.concepts} == {
            cls_.concept.suffix for cls_ in expected_info.concepts
        }
        assert {view.view.external_id for view in dms_rules.views} == {view.external_id for view in car.CAR_MODEL.views}
