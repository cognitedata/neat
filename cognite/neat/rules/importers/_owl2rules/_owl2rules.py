"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

from pathlib import Path
from typing import Literal, overload

from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph

from cognite.neat.rules.importers._base import BaseImporter
from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS
from cognite.neat.rules.validation import IssueList

from ._owl2classes import parse_owl_classes
from ._owl2metadata import parse_owl_metadata
from ._owl2properties import parse_owl_properties


class OWLImporter(BaseImporter):
    """Convert OWL ontology to tables/ transformation rules / Excel file.

        Args:
            owl_filepath: Path to OWL ontology

    !!! Note
        OWL Ontologies typically lacks some information that is required for making a complete
        data model. This means that the methods .to_rules() will typically fail. Instead, it is recommended
        that you use the .to_spreadsheet() method to generate an Excel file, and then manually add the missing
        information to the Excel file. The Excel file can then be converted to a `Rules` object.

        Alternatively, one can set the `make_compliant` parameter to True to allow neat to attempt to make
        the imported rules compliant by adding default values for missing information, attaching dangling
        properties to default containers based on the property type, etc. One has to be aware
        that NEAT will be opinionated about how to make the ontology compliant, and that the resulting
        rules may not be what you expect.

    """

    def __init__(self, owl_filepath: Path, make_compliant: bool = True):
        self.owl_filepath = owl_filepath
        self.make_compliant = make_compliant

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> InformationRules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[InformationRules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[InformationRules | None, IssueList] | InformationRules:
        if role is not None and role != RoleTypes.information_architect:
            raise ValueError(f"Role {role} is not supported for OWLImporter")

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
            "Metadata": parse_owl_metadata(graph, make_compliant=self.make_compliant),
            "Classes": parse_owl_classes(graph, make_compliant=self.make_compliant),
            "Properties": parse_owl_properties(graph, make_compliant=self.make_compliant),
        }

        if self.make_compliant:
            components = make_components_compliant(components)

        return InformationRules.model_validate(components)


def make_components_compliant(components: dict) -> dict:
    components = _add_missing_classes(components)
    components = _add_missing_value_types(components)

    return components


def _add_missing_classes(components: dict[str, list[dict]]) -> dict:
    """Add missing classes to Classes.

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing classes added to containers
    """

    missing_classes = {definition["Class"] for definition in components["Properties"]} - {
        definition["Class"] for definition in components["Classes"]
    }

    comment = (
        "Added by NEAT. "
        "This is a class that a domain of a property but was not defined in the ontology. "
        "It is added by NEAT to make the ontology compliant with CDF."
    )

    for class_ in missing_classes:
        components["Classes"].append({"Class": class_, "Comment": comment})

    return components


def _add_missing_value_types(components: dict) -> dict:
    """Add properties to classes that do not have any properties defined to them

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing properties added to containers
    """

    xsd_types = set(XSD_VALUE_TYPE_MAPPINGS.keys())
    value_types = {definition["Value Type"] for definition in components["Properties"]}

    classes = {definition["Class"] for definition in components["Classes"]}

    for class_ in value_types.difference(classes).difference(xsd_types):
        components["Classes"].append(
            {
                "Class": class_,
                "Comment": (
                    "Added by NEAT. "
                    "This is a class that a domain of a property but was not defined in the ontology. "
                    "It is added by NEAT to make the ontology compliant with CDF."
                ),
            }
        )

    return components
