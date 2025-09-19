from cognite.client.data_classes import LabelDefinitionList
from cognite.client.testing import monkeypatch_cognite_client
from rdflib import Graph

from tests.data import InstanceData
from thisisneat.core._instances.extractors import LabelsExtractor


def test_labels_extractor():
    with monkeypatch_cognite_client() as client_mock:
        client_mock.labels.return_value = LabelDefinitionList.load(InstanceData.AssetCentricCDF.labels_yaml.read_text())

    g = Graph()

    for triple in LabelsExtractor.from_dataset(client_mock, data_set_external_id="some labels").extract():
        g.add(triple)

    assert len(g) == 44
