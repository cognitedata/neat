from collections.abc import Iterable

from rdflib import RDF, Namespace, URIRef

from cognite.neat.core._shared import Triple
from cognite.neat.core._utils.rdf_ import split_uri

from ._base import BaseExtractor


class UnknownNamespaceExtractorMapper(BaseExtractor):
    """This extractor maps the output of another extractor to a new set of triples

    This does not require the namespace of the triples to be known ahead of the extraction.

    Args:
        extractor: The extractor to map.
        predicate_mapping: A mapping of predicates to new predicates.
        type_mapping: A mapping of types to new types.
    """

    def __init__(
        self,
        extractor: BaseExtractor,
        predicate_mapping: dict[str, str],
        type_mapping: dict[str, str],
    ) -> None:
        self.extractor = extractor
        self.predicate_mapping = predicate_mapping
        self.type_mapping = type_mapping

    def extract(self) -> Iterable[Triple]:
        """Extracts triples from the extractor and maps them to new predicates and types."""
        for subject, predicate, obj in self.extractor.extract():
            if predicate == RDF.type and isinstance(obj, URIRef):
                obj_namespace, obj_name = split_uri(obj)
                new_obj_name = self.type_mapping.get(obj_name, obj_name)
                obj = Namespace(obj_namespace)[new_obj_name]
            predicate_namespace, predicate_name = split_uri(predicate)
            new_predicate = self.predicate_mapping.get(predicate_name, predicate_name)
            predicate = Namespace(predicate_namespace)[new_predicate]
            yield subject, predicate, obj
