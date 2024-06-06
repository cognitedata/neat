from cognite.client.data_classes import TimeSeriesList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors import TimeSeriesExtractor
from tests.tests_unit.graph.test_extractors.constants import TIMESERIES_EXTRACTOR_DATA


def test_timeseries_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.time_series.return_value = TimeSeriesList.load(
            (TIMESERIES_EXTRACTOR_DATA / "dtu_v52_timeseries.yaml").read_text()
        )

    g = Graph()

    for triple in TimeSeriesExtractor.from_dataset(client_mock, data_set_external_id="nordic44").extract():
        g.add(triple)

    res = list(
        g.query(f"SELECT ?o WHERE {{ <{DEFAULT_NAMESPACE['1802374391833157']}> <{DEFAULT_NAMESPACE.concept_id}> ?o  }}")
    )

    assert len(g) == 2256
    assert URIRef("http://purl.org/aspect/wind_speed") == res[0][0]
