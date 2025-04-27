import warnings
from collections.abc import Iterable

from cognite.neat._issues.warnings import NeatWarning
from cognite.neat._shared import Triple
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.text import humanize_collection

from ._base import BaseExtractor


class ExcludePredicateExtractor(BaseExtractor):
    """This extractor maps the output of another extractor to a new set of triples

    This does not require the namespace of the triples to be known ahead of the extraction.

    Args:
        extractor: The extractor to map.
        exclude_predicates: A set of predicates to exclude from the extraction.
    """

    def __init__(
        self,
        extractor: BaseExtractor,
        exclude_predicates: set[str],
    ) -> None:
        self.extractor = extractor
        self.exclude_predicates = exclude_predicates
        self._found_predicates: set[str] = set()

    def extract(self) -> Iterable[Triple]:
        """Extracts triples from the extractor and maps them to new predicates and types."""
        for subject, predicate, obj in self.extractor.extract():
            predicate_str = remove_namespace_from_uri(predicate)
            if predicate_str in self.exclude_predicates:
                self._found_predicates.add(predicate_str)
                continue
            yield subject, predicate, obj

        not_found = self.exclude_predicates - self._found_predicates
        if not_found:
            warnings.warn(
                NeatWarning(
                    f"The following predicates were not found in the extraction: {humanize_collection(not_found)}."
                ),
                stacklevel=2,
            )
