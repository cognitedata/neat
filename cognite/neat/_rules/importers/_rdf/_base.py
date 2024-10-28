from pathlib import Path

from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD, Graph, Namespace, URIRef

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import FileReadError
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers._base import BaseImporter
from cognite.neat._rules.models.data_types import AnyURI
from cognite.neat._rules.models.entities import UnknownEntity
from cognite.neat._rules.models.information import (
    InformationInputRules,
)
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.rdf_ import get_namespace, uri_to_short_form

DEFAULT_NON_EXISTING_NODE_TYPE = AnyURI()


class BaseRDFImporter(BaseImporter[InformationInputRules]):
    """Baser RDF importers used for all rules importers that are using RDF as input.

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
        prefix: Prefix to be used for the imported rules
    """

    def __init__(
        self,
        issue_list: IssueList,
        graph: Graph,
        prefix: str,
        max_number_of_instance: int,
        non_existing_node_type: UnknownEntity | AnyURI,
    ) -> None:
        self.issue_list = issue_list
        self.graph = graph
        self.prefix = prefix
        self.max_number_of_instance = max_number_of_instance
        self.non_existing_node_type = non_existing_node_type

    @classmethod
    def from_graph_store(
        cls,
        store: NeatGraphStore,
        prefix: str = "neat",
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
    ):
        return cls(
            IssueList(title=f"{cls.__name__} issues"),
            store.graph,
            prefix=prefix,
            max_number_of_instance=max_number_of_instance,
            non_existing_node_type=non_existing_node_type,
        )

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        prefix: str = "neat",
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
    ):
        issue_list = IssueList(title=f"{cls.__name__} issues")

        graph = Graph()
        try:
            graph.parse(filepath)
        except Exception as e:
            issue_list.append(FileReadError(filepath, str(e)))

        # bind key namespaces
        graph.bind("owl", OWL)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("dcterms", DCTERMS)
        graph.bind("dc", DC)
        graph.bind("skos", SKOS)
        graph.bind("sh", SH)
        graph.bind("xsd", XSD)
        graph.bind("imf", "http://ns.imfid.org/imf#")

        return cls(
            issue_list,
            graph,
            prefix=prefix,
            max_number_of_instance=max_number_of_instance,
            non_existing_node_type=non_existing_node_type,
        )

    def to_rules(
        self,
    ) -> ReadRules[InformationInputRules]:
        """
        Creates `Rules` object from the data for target role.
        """

        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            return ReadRules(None, self.issue_list, {})

        rules_dict = self._to_rules_components()

        rules = InformationInputRules.load(rules_dict)

        self._add_transformation(rules)

        return ReadRules(rules, self.issue_list, {})

    def _to_rules_components(self) -> dict:
        raise NotImplementedError()

    @classmethod
    def _add_transformation(cls, rules: InformationInputRules) -> None:
        rules.prefixes = {}

        rules.prefixes[rules.metadata.prefix] = Namespace(rules.metadata.namespace)

        class_ref_dict = {}
        for class_ in rules.classes:
            if class_.reference:
                cls._add_uri_namespace_to_prefixes(URIRef(class_.reference), rules.prefixes)
                class_ref_dict[class_.class_] = f"{uri_to_short_form(URIRef(class_.reference), rules.prefixes)}"

        for property_ in rules.properties:
            if property_.reference:
                cls._add_uri_namespace_to_prefixes(URIRef(property_.reference), rules.prefixes)
                if class_id := class_ref_dict.get(property_.class_, None):
                    property_id = f"{uri_to_short_form(URIRef(property_.reference), rules.prefixes)}"
                    property_.transformation = f"{class_id}({property_id})"

    @classmethod
    def _add_uri_namespace_to_prefixes(cls, URI: URIRef, prefixes: dict[str, Namespace]):
        """Add URI to prefixes dict if not already present

        Args:
            URI: URI from which namespace is being extracted
            prefixes: Dict of prefixes and namespaces
        """
        if Namespace(get_namespace(URI)) not in prefixes.values():
            prefixes[f"prefix-{len(prefixes)+1}"] = Namespace(get_namespace(URI))
