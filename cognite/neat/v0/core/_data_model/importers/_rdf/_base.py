from datetime import datetime
from pathlib import Path
from typing import Any

from cognite.client import data_modeling as dm
from rdflib import Graph, Namespace, URIRef
from typing_extensions import Self

from cognite.neat.v0.core._constants import get_default_prefixes_and_namespaces
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.importers._base import BaseImporter
from cognite.neat.v0.core._data_model.models._base_verified import RoleTypes
from cognite.neat.v0.core._data_model.models.conceptual import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.v0.core._data_model.models.data_types import AnyURI
from cognite.neat.v0.core._data_model.models.entities import UnknownEntity
from cognite.neat.v0.core._issues import IssueList, MultiValueError
from cognite.neat.v0.core._issues.errors import FileReadError
from cognite.neat.v0.core._issues.errors._general import NeatValueError
from cognite.neat.v0.core._store import NeatInstanceStore
from cognite.neat.v0.core._utils.rdf_ import get_namespace

DEFAULT_NON_EXISTING_NODE_TYPE = AnyURI()


DEFAULT_RDF_DATA_MODEL_ID = ("neat_space", "RDFDataModel", "rdf")


class BaseRDFImporter(BaseImporter[UnverifiedConceptualDataModel]):
    """Baser RDF importers used for all data model importers that are using RDF as input.

    Args:
        issue_list: Issue list to store issues
        graph: graph where instances are stored
        data_model_id: Data model id to be used for the imported data model
        space: CDF Space to be used for the imported data model
        language: Language for description and human readable entity names



    !!! note "Language"
        Language is provided as ISO 639-1 code. If not provided, English will be used as default.

    """

    def __init__(
        self,
        issue_list: IssueList,
        graph: Graph,
        data_model_id: dm.DataModelId | tuple[str, str, str],
        max_number_of_instance: int,
        non_existing_node_type: UnknownEntity | AnyURI,
        language: str,
        source_name: str = "Unknown",
    ) -> None:
        self.issue_list = issue_list
        self.graph = graph
        self.data_model_id = dm.DataModelId.load(data_model_id)
        if self.data_model_id.version is None:
            raise NeatValueError("Version is required when setting a Data Model ID")

        self.max_number_of_instance = max_number_of_instance
        self.non_existing_node_type = non_existing_node_type
        self.language = language
        self.source_name = source_name

    @classmethod
    def from_graph_store(
        cls,
        store: NeatInstanceStore,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_RDF_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        language: str = "en",
    ) -> Self:
        return cls(
            IssueList(title=f"{cls.__name__} issues"),
            store.dataset,
            data_model_id=data_model_id,
            max_number_of_instance=max_number_of_instance,
            non_existing_node_type=non_existing_node_type,
            language=language,
        )

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_RDF_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        language: str = "en",
        source_name: str = "Unknown",
    ) -> Self:
        issue_list = IssueList(title=f"{cls.__name__} issues")

        graph = Graph()
        try:
            graph.parse(filepath)
        except Exception as e:
            issue_list.append(FileReadError(filepath, str(e)))

        # bind key namespaces
        for prefix, namespace in get_default_prefixes_and_namespaces().items():
            graph.bind(prefix, namespace)

        return cls(
            issue_list,
            graph,
            data_model_id=data_model_id,
            max_number_of_instance=max_number_of_instance,
            non_existing_node_type=non_existing_node_type,
            language=language,
            source_name=source_name,
        )

    def to_data_model(
        self,
    ) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        """
        Creates `ImportedDataModel` object from the data for target role.
        """
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_data_model method will return None
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        data_model_dict = self._to_data_model_components()

        data_model = UnverifiedConceptualDataModel.load(data_model_dict)
        self.issue_list.trigger_warnings()
        return ImportedDataModel(data_model)

    def _to_data_model_components(self) -> dict:
        raise NotImplementedError()

    @classmethod
    def _add_uri_namespace_to_prefixes(cls: Any, URI: URIRef, prefixes: dict[str, Namespace]) -> None:
        """Add URI to prefixes dict if not already present

        Args:
            URI: URI from which namespace is being extracted
            prefixes: Dict of prefixes and namespaces
        """
        if Namespace(get_namespace(URI)) not in prefixes.values():
            prefixes[f"prefix_{len(prefixes) + 1}"] = Namespace(get_namespace(URI))

    @property
    def _metadata(self) -> dict:
        return {
            "role": RoleTypes.information,
            "space": self.data_model_id.space,
            "external_id": self.data_model_id.external_id,
            "version": self.data_model_id.version,
            "created": datetime.now().replace(microsecond=0),
            "updated": datetime.now().replace(microsecond=0),
            "name": None,
            "description": f"Data model imported using {type(self).__name__}",
            "creator": "Neat",
        }
