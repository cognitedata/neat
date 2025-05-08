from cognite.client.data_classes import Row
from rdflib import RDF, Literal

from cognite.neat.core._client.testing import monkeypatch_neat_client
from cognite.neat.core._instances.extractors import RAWExtractor


class TestRAWExtractor:
    def test_extract_triples(self) -> None:
        with monkeypatch_neat_client() as client:
            client.raw.rows.return_value = [
                Row(key="key1", columns={"column1": "value1", "column2": "value2"}),
                Row(key="key2", columns={"column1": "value3", "column2": "value4"}),
            ]
        extractor = RAWExtractor(client, "my_db", "my_table")
        ns = extractor.namespace

        triples = set(extractor.extract())

        assert triples == {
            (ns["key1"], RDF.type, ns["my_table"]),
            (ns["key1"], ns["column1"], Literal("value1")),
            (ns["key1"], ns["column2"], Literal("value2")),
            (ns["key2"], RDF.type, ns["my_table"]),
            (ns["key2"], ns["column1"], Literal("value3")),
            (ns["key2"], ns["column2"], Literal("value4")),
        }
