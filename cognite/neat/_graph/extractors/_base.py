from abc import abstractmethod
from collections.abc import Iterable

from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._shared import Triple
from cognite.neat._utils.auxiliary import class_html_doc


class BaseExtractor:
    """This is the base class for all extractors. It defines the interface that
    extractors must implement.
    """

    def _get_activity_names(self) -> list[str]:
        """Returns the name of the activities that the extractor performs,
        i.e., the actions that it performs when you call extract().."""
        # This method can be overridden by subclasses that runs multiple extractors
        # for example the ClassicGraphExtractor
        return [type(self).__name__]

    @abstractmethod
    def extract(self) -> Iterable[Triple]:
        raise NotImplementedError()

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls)


class KnowledgeGraphExtractor(BaseExtractor):
    """A knowledge graph extractor extracts triples from a knowledge graph and
    have a schema for the triples that it extracts.
    """

    @abstractmethod
    def get_information_rules(self) -> InformationRules:
        """Returns the information rules that the extractor uses."""
        raise NotImplementedError()


class DMSGraphExtractor(KnowledgeGraphExtractor):
    @abstractmethod
    def get_dms_rules(self) -> DMSRules:
        """Returns the DMS rules that the extractor uses."""
        raise NotImplementedError()
