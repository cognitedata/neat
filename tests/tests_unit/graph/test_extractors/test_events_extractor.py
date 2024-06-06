from cognite.client.data_classes import EventList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.graph.extractors import EventsExtractor
from tests.tests_unit.graph.test_extractors.constants import EVENTS_EXTRACTOR_DATA


def test_events_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.events.return_value = EventList.load((EVENTS_EXTRACTOR_DATA / "dtu_v52_events.yaml").read_text())

    g = Graph()

    for triple in EventsExtractor.from_dataset(client_mock, data_set_external_id="dtu_v52_events").extract():
        g.add(triple)

    assert len(g) == 568
