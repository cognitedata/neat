import urllib.parse
from collections.abc import Iterable

from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.extractors import BaseExtractor, ExcludePredicateExtractor
from cognite.neat._issues import catch_warnings
from cognite.neat._shared import Triple


class TestExcludeExtractorMapping:
    def test_extract(self) -> None:
        namespace = Namespace("http://example.org/")
        my_instance = namespace["my_instance"]

        class MockExtractor(BaseExtractor):
            def extract(self) -> Iterable[Triple]:
                yield my_instance, RDF.type, namespace["myType"]
                yield my_instance, namespace["prop1"], Literal(1)
                yield my_instance, namespace[urllib.parse.quote("prop2どさじざ")], Literal(2)
                yield my_instance, namespace["prop3"], Literal(3)

        extractor = MockExtractor()

        mapper = ExcludePredicateExtractor(
            extractor,
            {"prop2どさじざ", "prop4"},
        )
        with catch_warnings() as issues:
            triples = list(mapper.extract())

        assert len(issues) == 1
        assert (
            issues[0].as_message()
            == "NeatValueWarning: The following predicates were not found in the extraction: prop4."
        )

        assert len(triples) == 3
        assert triples[0] == (my_instance, RDF.type, namespace["myType"])
        assert triples[1] == (my_instance, namespace["prop1"], Literal(1))
        assert triples[2] == (my_instance, namespace["prop3"], Literal(3))
