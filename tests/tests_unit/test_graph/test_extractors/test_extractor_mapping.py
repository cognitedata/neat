from collections.abc import Iterable

from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.extractors import BaseExtractor, ExtractorMapper
from cognite.neat._shared import Triple


class TestExtractorMapping:
    def test_extractor_mapper(self) -> None:
        namespace = Namespace("http://example.org/")

        class MockExtractor(BaseExtractor):
            def extract(self) -> Iterable[Triple]:
                my_instance = namespace["my_instance"]
                yield my_instance, RDF.type, namespace["my#$type"]
                yield my_instance, namespace["イ覧誠んしは"], Literal(1)

        extractor = MockExtractor()

        mapper = ExtractorMapper(
            extractor,
            {namespace["イ覧誠んしは"]: namespace["myProperty"]},
            {namespace["my#$type"]: namespace["MyType"]},
        )
        triples = list(mapper.extract())

        assert len(triples) == 2
        assert triples[0] == (namespace["my_instance"], RDF.type, namespace["MyType"])
        assert triples[1] == (namespace["my_instance"], namespace["myProperty"], Literal(1))
