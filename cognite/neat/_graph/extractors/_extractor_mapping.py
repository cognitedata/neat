from collections.abc import Iterable

from rdflib import RDF, Literal, URIRef

from cognite.neat._shared import Triple

from ._base import BaseExtractor


class ExtractorMapper(BaseExtractor):
    """This extractor maps the output of another extractor to a new set of triples.

    This is used to transform the output of an extractor before the triples are written
    to the graph. The motivation for this is that changing triples before they are written
    is much cheaper than changing them after they are written to the graph.

    The original motivating use case for this was to map a source system properties to properties
    that are compatible with the information model property regex.

    Args:
        extractor: The extractor to map.
        predicate_mapping: A mapping of predicates to new predicates.
        type_mapping: A mapping of types to new types.
    """

    def __init__(
        self,
        extractor: BaseExtractor,
        predicate_mapping: dict[URIRef, URIRef],
        type_mapping: dict[URIRef | Literal, URIRef | Literal],
    ) -> None:
        self.extractor = extractor
        self.predicate_mapping = predicate_mapping
        self.type_mapping = type_mapping

    def extract(self) -> Iterable[Triple]:
        """Extracts triples from the extractor and maps them to new predicates and types."""
        for subject, predicate, obj in self.extractor.extract():
            if predicate == RDF.type:
                obj = self.type_mapping.get(obj, obj)
            predicate = self.predicate_mapping.get(predicate, predicate)
            yield subject, predicate, obj
