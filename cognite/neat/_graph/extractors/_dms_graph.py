from collections.abc import Iterable

from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._shared import Triple

from ._base import KnowledgeGraphExtractor


class DMSGraphExtractor(KnowledgeGraphExtractor):
    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()

    def get_information_rules(self) -> InformationRules:
        """Returns the information rules that the extractor uses."""
        raise NotImplementedError()

    def get_dms_rules(self) -> DMSRules:
        """Returns the DMS rules that the extractor uses."""
        raise NotImplementedError()
