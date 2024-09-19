from pathlib import Path

from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SH, SKOS, XSD, Graph

from cognite.neat.issues import IssueList
from cognite.neat.issues.errors import FileReadError
from cognite.neat.rules._shared import ReadRules
from cognite.neat.rules.importers._base import BaseImporter
from cognite.neat.rules.models.information import (
    InformationInputRules,
)
from cognite.neat.store import NeatGraphStore


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
    ) -> None:
        self.issue_list = issue_list
        self.graph = graph
        self.prefix = prefix
        self.max_number_of_instance = max_number_of_instance

    @classmethod
    def from_graph_store(
        cls,
        store: NeatGraphStore,
        prefix: str = "neat",
        max_number_of_instance: int = -1,
    ):
        return cls(
            IssueList(title=f"{cls.__name__} issues"),
            store.graph,
            prefix=prefix,
            max_number_of_instance=max_number_of_instance,
        )

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        prefix: str = "neat",
        max_number_of_instance: int = -1,
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
        return ReadRules(rules, self.issue_list, {})

    def _to_rules_components(self) -> dict:
        raise NotImplementedError()
