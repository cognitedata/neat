"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

from pathlib import Path
from typing import Literal, overload

from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph

from cognite.neat.issues import IssueList
from cognite.neat.rules.importers._base import BaseImporter, VerifiedRules
from cognite.neat.rules.importers._rdf._shared import make_components_compliant
from cognite.neat.rules.models import InformationRules, RoleTypes

from ._owl2classes import parse_owl_classes
from ._owl2metadata import parse_owl_metadata
from ._owl2properties import parse_owl_properties


class OWLImporter(BaseImporter):
    """Convert OWL ontology to tables/ transformation rules / Excel file.

        Args:
            filepath: Path to OWL ontology

    !!! Note
        OWL Ontologies are information models which completeness varies. As such, constructing functional
        data model directly will often be impossible, therefore the produced Rules object will be ill formed.
        To avoid this, neat will automatically attempt to make the imported rules compliant by adding default
        values for missing information, attaching dangling properties to default containers based on the
        property type, etc.

        One has to be aware that NEAT will be opinionated about how to make the ontology
        compliant, and that the resulting rules may not be what you expect.

    """

    def __init__(self, filepath: Path):
        self.owl_filepath = filepath

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> VerifiedRules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[VerifiedRules | None, IssueList]: ...

    def to_rules(
        self,
        errors: Literal["raise", "continue"] = "continue",
        role: RoleTypes | None = None,
    ) -> tuple[VerifiedRules | None, IssueList] | VerifiedRules:
        graph = Graph()
        try:
            graph.parse(self.owl_filepath)
        except Exception as e:
            raise Exception(f"Could not parse owl file: {e}") from e

        # bind key namespaces
        graph.bind("owl", OWL)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("dcterms", DCTERMS)
        graph.bind("dc", DC)
        graph.bind("skos", SKOS)

        components = {
            "Metadata": parse_owl_metadata(graph),
            "Classes": parse_owl_classes(graph),
            "Properties": parse_owl_properties(graph),
        }

        components = make_components_compliant(components)

        rules = InformationRules.model_validate(components)
        return self._to_output(rules, IssueList(), errors, role)
