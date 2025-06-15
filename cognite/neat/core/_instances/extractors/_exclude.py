import urllib.parse
import warnings
from collections.abc import Iterable

from cognite.neat.core._issues.warnings import NeatValueWarning
from cognite.neat.core._shared import Triple
from cognite.neat.core._utils.rdf_ import remove_namespace_from_uri
from cognite.neat.core._utils.text import humanize_collection

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
            predicate_str = urllib.parse.unquote(remove_namespace_from_uri(predicate))
            if predicate_str in self.exclude_predicates:
                self._found_predicates.add(predicate_str)
                continue
            yield subject, predicate, obj

        not_found = self.exclude_predicates - self._found_predicates
        if not_found:
            warnings.warn(
                NeatValueWarning(
                    "The following predicates were not found in "
                    f"the extraction: {humanize_collection(list(not_found))}."
                ),
                stacklevel=2,
            )
