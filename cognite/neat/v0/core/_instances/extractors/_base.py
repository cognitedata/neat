from abc import abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING

from rdflib import URIRef

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model.models import ConceptualDataModel
from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._utils.auxiliary import class_html_doc

if TYPE_CHECKING:
    from cognite.neat.v0.core._store._provenance import Agent as ProvenanceAgent


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
    """A knowledge graph extractor extracts triples with a schema"""

    @abstractmethod
    def get_conceptual_data_model(self) -> ConceptualDataModel:
        """Returns the conceptual data model that the extractor uses."""
        raise NotImplementedError()

    @property
    def description(self) -> str:
        return self.__doc__.strip().split("\n")[0] if self.__doc__ else "Missing"

    @property
    def source_uri(self) -> URIRef:
        raise NotImplementedError

    @property
    def agent(self) -> "ProvenanceAgent":
        """Provenance agent for the importer."""
        from cognite.neat.v0.core._store._provenance import Agent as ProvenanceAgent

        return ProvenanceAgent(id_=DEFAULT_NAMESPACE[f"agent/{type(self).__name__}"])
