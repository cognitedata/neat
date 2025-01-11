from collections.abc import Iterable, Sequence
from typing import Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes import Source
from cognite.client.data_classes.data_modeling.instances import Instance

from cognite.neat._client.testing import monkeypatch_neat_client
from cognite.neat._graph.extractors import DMSGraphExtractor
from tests.data import car


def car_instances(
    instance_type: Literal["node", "edge"] = "node", sources: Source | Sequence[Source] | None = None, **_
) -> Iterable[Instance]:
    for instance in car.INSTANCES:
        if instance_type == "node" and isinstance(instance, dm.EdgeApply):
            continue
        if instance_type == "edge" and isinstance(instance, dm.NodeApply):
            continue
        if sources is not None and instance.sources and instance.sources[0].source not in sources:
            continue
        yield as_read(instance)


def as_read(instance: dm.NodeApply | dm.EdgeApply) -> Instance:
    args = dict(
        space=instance.space,
        external_id=instance.external_id,
        type=instance.type,
        last_updated_time=0,
        created_time=0,
        version=instance.existing_version,
        deleted_time=None,
        properties={source.source: source.properties for source in instance.sources or []},
    )
    if isinstance(instance, dm.NodeApply):
        return dm.Node(**args)
    else:
        return dm.Edge(
            start_node=instance.start_node,
            end_node=instance.end_node,
            **args,
        )


def as_read_containers(containers: Sequence[dm.ContainerApply]) -> dm.ContainerList:
    return dm.ContainerList(
        [
            dm.Container(
                space=c.space,
                external_id=c.external_id,
                properties=c.properties,
                is_global=c.space.startswith("cdf"),
                last_updated_time=0,
                created_time=0,
                description=c.description,
                name=c.name,
                used_for=c.used_for or "all",
                constraints=c.constraints,
                indexes=c.indexes,
            )
            for c in containers
        ]
    )


def as_read_space(space: dm.SpaceApply) -> dm.Space:
    return dm.Space(
        space=space.space,
        last_updated_time=0,
        created_time=0,
        description=space.description,
        name=space.name,
        is_global=space.space.startswith("cdf"),
    )


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
        assert {cls_.class_ for cls_ in info_rules.classes} == {cls_.class_ for cls_ in expected_info.classes}
        assert {view.view.external_id for view in dms_rules.views} == {view.external_id for view in car.CAR_MODEL.views}
