from datetime import datetime
from pathlib import Path

from cognite.client import data_modeling as dm
from rdflib import Graph, Namespace, URIRef

from cognite.neat._constants import get_default_prefixes_and_namespaces
from cognite.neat._issues import IssueList, MultiValueError
from cognite.neat._issues.errors import FileReadError
from cognite.neat._issues.errors._general import NeatValueError
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers._base import BaseImporter
from cognite.neat._rules.models._base_rules import RoleTypes
from cognite.neat._rules.models.data_types import AnyURI
from cognite.neat._rules.models.entities import UnknownEntity
from cognite.neat._rules.models.information import InformationInputRules
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.rdf_ import get_namespace

DEFAULT_NON_EXISTING_NODE_TYPE = AnyURI()


DEFAULT_RDF_DATA_MODEL_ID = ("neat_space", "RDFDataModel", "rdf")


class BaseRDFImporter(BaseImporter[InformationInputRules]):
    """Baser RDF importers used for all rules importers that are using RDF as input.

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
        data_model_id: Data model id to be used for the imported rules
        space: CDF Space to be used for the imported rules
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
        store: NeatGraphStore,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_RDF_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        language: str = "en",
    ):
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
    ):
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

    def to_rules(
        self,
    ) -> ReadRules[InformationInputRules]:
        """
        Creates `Rules` object from the data for target role.
        """
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        rules_dict = self._to_rules_components()

        rules = InformationInputRules.load(rules_dict)
        self.issue_list.trigger_warnings()
        return ReadRules(rules, {})

    def _to_rules_components(self) -> dict:
        raise NotImplementedError()

    @classmethod
    def _add_uri_namespace_to_prefixes(cls, URI: URIRef, prefixes: dict[str, Namespace]):
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
