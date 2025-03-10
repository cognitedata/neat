from collections.abc import Iterable
from typing import Literal
from unittest.mock import MagicMock

from cognite.client import data_modeling as dm
from cognite.client.data_classes import Source
from cognite.client.data_classes.data_modeling.instances import Instance
from requests import Response

from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._graph.extractors import DMSGraphExtractor
from tests.data import car
from tests.utils import as_read_containers, as_read_instance, as_read_space

_IS_CALLED = False


def car_instances(
    instance_type: Literal["node", "edge"] = "node", source: Source | None = None, **other_args
) -> Iterable[Instance]:
    global _IS_CALLED
    if _IS_CALLED:
        return
    for instance in car.INSTANCES:
        yield as_read_instance(instance)
    _IS_CALLED = True


class TestDMSGraphExtractor:
    def test_extract_car_example(self) -> None:
        with monkeypatch_neat_client() as client:
            response = MagicMock(spec=Response)
            response.json.return_value = {"items": [item.dump() for item in car_instances()], "nextCursor": None}
            client.post.return_value = response
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
