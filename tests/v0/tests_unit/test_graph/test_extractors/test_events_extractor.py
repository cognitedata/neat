from cognite.client.data_classes import EventList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.v0.core._instances.extractors import EventsExtractor
from tests.v0.data import InstanceData


def test_events_extractor():
    with monkeypatch_cognite_client() as client_mock:
        events = EventList.load(InstanceData.AssetCentricCDF.events_yaml.read_text())
        client_mock.events.return_value = events
        client_mock.events.aggregate_count.return_value = len(events)

    g = Graph()

    for triple in EventsExtractor.from_dataset(client_mock, data_set_external_id="some_event_dataset").extract():
        g.add(triple)

    assert len(g) == 18
