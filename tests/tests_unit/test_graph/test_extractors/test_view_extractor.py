from cognite.neat._graph.extractors import ViewExtractor
from tests.data import GraphData

from .test_dms_extractor import instance_apply_to_read


class TestViewExtractor:
    def test_extract_instances(self) -> None:
        view_id = GraphData.car.CAR_MODEL.views[0].as_id()
        extractor = ViewExtractor(
            view_id=view_id,
            instances=instance_apply_to_read(
                instance
                for instance in GraphData.car.INSTANCES
                if instance.sources and instance.sources[0].source == view_id
            ),
        )
        expected_triples = {
            triple
            for triple in GraphData.car.TRIPLES
            if (
                triple[0] in {GraphData.car._instance_ns["Car1"], GraphData.car._instance_ns["Car2"]}
                and triple[1] != GraphData.car._model_ns["Car.Manufacturer"]
            )
        }

        triples = set(extractor.extract())

        assert expected_triples == triples
