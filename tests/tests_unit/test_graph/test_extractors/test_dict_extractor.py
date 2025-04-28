from rdflib import Literal, Namespace

from cognite.neat._graph.extractors import DictExtractor


class TestDictExtractor:
    def test_extract_with_empty_values(self) -> None:
        namespace = Namespace("http://example.org/")
        id_ = namespace["my_instance"]
        extractor = DictExtractor(
            id_=id_,
            data={
                "myProperty": "value",
                "myEmptyProperty": "",
            },
            namespace=namespace,
            empty_values=set(),
        )

        triples = list(extractor.extract())

        assert len(triples) == 2
        assert triples[0] == (id_, namespace["myProperty"], Literal("value"))
        assert triples[1] == (id_, namespace["myEmptyProperty"], Literal(""))
