from abc import ABC, abstractmethod
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic

from rdflib import URIRef

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model._shared import (
    ImportedDataModel,
    T_UnverifiedDataModel,
)
from cognite.neat.v0.core._utils.auxiliary import class_html_doc

if TYPE_CHECKING:
    from cognite.neat.v0.core._store._provenance import Agent as ProvenanceAgent


class BaseImporter(ABC, Generic[T_UnverifiedDataModel]):
    """
    BaseImporter class which all data model importers inherit from.
    """

    @abstractmethod
    def to_data_model(self) -> ImportedDataModel[T_UnverifiedDataModel]:
        """Creates `DataModel` object from the data for target role."""
        raise NotImplementedError()

    def _default_metadata(self) -> dict[str, Any]:
        creator = "UNKNOWN"
        with suppress(KeyError, ImportError):
            import getpass

            creator = getpass.getuser()

        return {
            "space": "neat",
            "external_id": "NeatImportedDataModel",
            "version": "0.1.0",
            "name": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "updated": datetime.now().replace(microsecond=0).isoformat(),
            "creator": creator,
            "description": f"Imported using {type(self).__name__}",
        }

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls)

    @property
    def agent(self) -> "ProvenanceAgent":
        """Provenance agent for the importer."""
        from cognite.neat.v0.core._store._provenance import Agent as ProvenanceAgent

        return ProvenanceAgent(id_=DEFAULT_NAMESPACE[f"agent/{type(self).__name__}"])

    @property
    def description(self) -> str:
        return "MISSING DESCRIPTION"

    @property
    def source_uri(self) -> URIRef:
        return DEFAULT_NAMESPACE["UNKNOWN"]
