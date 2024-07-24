"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

from pathlib import Path
from typing import Literal, overload

from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph

from cognite.neat.rules.importers._base import BaseImporter, Rules
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models import InformationRules, RoleTypes
from cognite.neat.rules.models.data_types import _XSD_TYPES

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
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
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


def make_components_compliant(components: dict) -> dict:
    components = _add_missing_classes(components)
    components = _add_missing_value_types(components)
    components = _add_default_property_to_dangling_classes(components)

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

    xsd_types = _XSD_TYPES
    candidate_value_types = {definition["Value Type"] for definition in components["Properties"]} - {
        definition["Class"] for definition in components["Classes"]
    }

    # to avoid issue of case sensitivity for xsd types
    value_types_lower = {v.lower() for v in candidate_value_types}

    xsd_types_lower = {x.lower() for x in xsd_types}

    # Create a mapping from lowercase strings to original strings
    value_types_mapping = {v.lower(): v for v in candidate_value_types}

    # Find the difference
    difference = value_types_lower - xsd_types_lower

    # Convert the difference back to the original case
    difference_original_case = {value_types_mapping[d] for d in difference}

    for class_ in difference_original_case:
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


def _add_default_property_to_dangling_classes(components: dict[str, list[dict]]) -> dict:
    """Add missing classes to Classes.

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing classes added to containers
    """

    dangling_classes = {
        definition["Class"] for definition in components["Classes"] if not definition.get("Parent Class", None)
    } - {definition["Class"] for definition in components["Properties"]}

    comment = (
        "Added by NEAT. "
        "This is property has been added to this class since otherwise it will create "
        "dangling classes in the ontology."
    )

    for class_ in dangling_classes:
        components["Properties"].append(
            {
                "Class": class_,
                "Property": "label",
                "Value Type": "string",
                "Comment": comment,
                "Min Count": 0,
                "Max Count": 1,
                "Reference": "http://www.w3.org/2000/01/rdf-schema#label",
            }
        )

    return components
