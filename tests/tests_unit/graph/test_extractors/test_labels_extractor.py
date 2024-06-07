from cognite.client.data_classes import LabelDefinitionList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from cognite.neat.graph.extractors import LabelsExtractor
from tests.tests_unit.graph.test_extractors.constants import CLASSIC_CDF_EXTRACTOR_DATA


def test_labels_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.labels.return_value = LabelDefinitionList.load(
            (CLASSIC_CDF_EXTRACTOR_DATA / "labels.yaml").read_text()
        )

    g = Graph()

    for triple in LabelsExtractor.from_dataset(client_mock, data_set_external_id="some labels").extract():
        g.add(triple)

    assert len(g) == 44
