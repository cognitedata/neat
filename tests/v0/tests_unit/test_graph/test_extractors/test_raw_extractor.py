from cognite.client.data_classes import Row
from rdflib import RDF, XSD, Literal

from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._instances.extractors import RAWExtractor


class TestRAWExtractor:
    def test_extract_triples(self) -> None:
        with monkeypatch_neat_client() as client:
            client.raw.rows.return_value = [
                Row(
                    key="key1",
                    columns={"column1": "value1", "column2": "100", "column3": "1983-01-22", "column4": "key2"},
                ),
                Row(
                    key="key2",
                    columns={"column1": "value3", "column2": "200", "column3": "1983-01-22", "column4": "key1"},
                ),
            ]
        extractor = RAWExtractor(client, "my_db", "my_table", str_to_ideal_type=True, foreign_keys={"column4"})
        ns = extractor.namespace

        triples = set(extractor.extract())

        assert triples == {
            (ns["key1"], RDF.type, ns["my_table"]),
            (ns["key1"], ns["column1"], Literal("value1")),
            (ns["key1"], ns["column2"], Literal("100", datatype=XSD.integer)),
            (ns["key1"], ns["column3"], Literal("1983-01-22T00:00:00", datatype=XSD.dateTime)),
            (ns["key1"], ns["column4"], ns["key2"]),
            (ns["key2"], RDF.type, ns["my_table"]),
            (ns["key2"], ns["column1"], Literal("value3")),
            (ns["key2"], ns["column2"], Literal("200", datatype=XSD.integer)),
            (ns["key2"], ns["column3"], Literal("1983-01-22T00:00:00", datatype=XSD.dateTime)),
            (ns["key2"], ns["column4"], ns["key1"]),
        }
