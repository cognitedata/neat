"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

from pathlib import Path

import pandas as pd
from pydantic_core import ErrorDetails
from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph

from cognite.neat.rules.importer._base import BaseImporter
from cognite.neat.rules.models.raw_rules import RawRules
from cognite.neat.rules.models.rules import Rules
from cognite.neat.rules.models.tables import Tables

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
        information to the Excel file. The Excel file can then be converted to a TransformationRules object.

        One can set the `make_compliant` parameter to True to allow neat to attempt to make
        the rules compliant by adding default values for missing information, attaching dangling
        properties to default containers based on the property type, etc.

    """

    def __init__(self, owl_filepath: Path):
        self.owl_filepath = owl_filepath

    def to_tables(self, make_compliant: bool = False) -> dict[str, pd.DataFrame]:
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

        tables: dict[str, pd.DataFrame] = {
            Tables.metadata: parse_owl_metadata(graph, make_compliant=make_compliant),
            Tables.classes: parse_owl_classes(graph, make_compliant=make_compliant),
            Tables.properties: parse_owl_properties(graph, make_compliant=make_compliant),
        }

        if make_compliant:
            tables = _add_missing_classes(tables)
            tables = _add_properties_to_dangling_classes(tables)
            tables = _add_missing_value_types(tables)
            tables = _add_entity_type_property(tables)
        # add sorting of classes and properties prior exporting

        return tables

    def to_raw_rules(self, make_compliant: bool = False) -> RawRules:
        """Creates `RawRules` object from the data."""

        tables = self.to_tables(make_compliant=make_compliant)

        return RawRules.from_tables(tables=tables, importer_type=self.__class__.__name__)

    def to_rules(
        self,
        return_report: bool = False,
        skip_validation: bool = False,
        validators_to_skip: list[str] | None = None,
        make_compliant: bool = False,
    ) -> tuple[Rules | None, list[ErrorDetails] | None, list | None] | Rules:
        """
        Creates `Rules` object from the data.

        Args:
            return_report: To return validation report. Defaults to False.
            skip_validation: Bypasses Rules validation. Defaults to False.
            validators_to_skip: List of validators to skip. Defaults to None.
            make_compliant: Flag for generating compliant rules, by default False

        Returns:
            Instance of `Rules`, which can be validated, not validated based on
            `skip_validation` flag, or partially validated if `validators_to_skip` is set,
            and optional list of errors and warnings if
            `return_report` is set to True.

        !!! Note "Skip Validation
            `skip_validation` flag should be only used for purpose when `Rules` object
            is exported to an Excel file. Do not use this flag for any other purpose!
        """

        raw_rules = self.to_raw_rules(make_compliant=make_compliant)

        return raw_rules.to_rules(return_report, skip_validation, validators_to_skip)


def _add_missing_classes(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add missing classes to containers.

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing classes added to containers
    """

    return tables


def _add_properties_to_dangling_classes(
    tables: dict[str, pd.DataFrame], properties_to_add: list[str] | None = None
) -> dict[str, pd.DataFrame]:
    """Add properties to classes that do not have any properties defined to them

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing properties added to containers
    """

    if properties_to_add is None:
        properties_to_add = ["label", "entityType"]
    return tables


def _add_missing_value_types(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add properties to classes that do not have any properties defined to them

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing properties added to containers
    """

    return tables


def _add_entity_type_property(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return tables
