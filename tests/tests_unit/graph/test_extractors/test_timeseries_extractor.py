from cognite.client.data_classes import TimeSeriesList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.graph.extractors import TimeSeriesExtractor
from tests.config import CLASSIC_CDF_EXTRACTOR_DATA


def test_timeseries_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.time_series.return_value = TimeSeriesList.load(
            (CLASSIC_CDF_EXTRACTOR_DATA / "timeseries.yaml").read_text()
        )

    g = Graph()

    for triple in TimeSeriesExtractor.from_dataset(client_mock, data_set_external_id="some data set").extract():
        g.add(triple)

    assert len(g) == 20
