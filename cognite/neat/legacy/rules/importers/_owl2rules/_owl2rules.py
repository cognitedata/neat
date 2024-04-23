"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

from pathlib import Path

import pandas as pd
from pydantic_core import ErrorDetails
from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph

from cognite.neat.legacy.rules.importers._base import BaseImporter
from cognite.neat.legacy.rules.models.raw_rules import RawRules
from cognite.neat.legacy.rules.models.rules import Rules
from cognite.neat.legacy.rules.models.tables import Tables
from cognite.neat.legacy.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS

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
            tables = make_tables_compliant(tables)
        # add sorting of classes and properties prior exporting

        tables[Tables.classes] = tables[Tables.classes].sort_values(by=["Class"])
        tables[Tables.properties] = tables[Tables.properties].sort_values(by=["Class", "Property"])

        return tables

    def to_raw_rules(self, make_compliant: bool = False) -> RawRules:
        """Creates `RawRules` object from the data."""

        tables = self.to_tables(make_compliant=make_compliant)

        return RawRules.from_tables(tables=tables, importer_type=self.__class__.__name__)

    def to_rules(
        self,
        return_report: bool = False,
        skip_validation: bool = False,
        validators_to_skip: set[str] | None = None,
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


def make_tables_compliant(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    tables = _add_missing_classes(tables)
    tables = _add_missing_value_types(tables)
    tables = _add_properties_to_dangling_classes(tables)
    tables = _add_entity_type_property(tables)

    return tables


def _add_missing_classes(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add missing classes to containers.

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing classes added to containers
    """

    missing_classes = set(tables[Tables.properties].Class.to_list()) - set(tables[Tables.classes].Class.to_list())

    rows = []
    for class_ in missing_classes:
        rows += [
            {
                "Class": class_,
                "Name": None,
                "Description": None,
                "Parent Class": None,
                "Deprecated": False,
                "Deprecation Date": None,
                "Replaced By": None,
                "Source": None,
                "Source Entity Name": None,
                "Match Type": None,
                "Comment": (
                    "Added by NEAT. "
                    "This is a class that a domain of a property but was not defined in the ontology. "
                    "It is added by NEAT to make the ontology compliant with CDF."
                ),
            }
        ]

    if rows:
        tables[Tables.classes] = pd.concat(
            [tables[Tables.classes], pd.DataFrame(rows)],
            ignore_index=True,
        )

    return tables


def _add_missing_value_types(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add properties to classes that do not have any properties defined to them

    Args:
        tables: imported tables from owl ontology

    Returns:
        Updated tables with missing properties added to containers
    """

    xsd_types = set(XSD_VALUE_TYPE_MAPPINGS.keys())
    referred_types = set(tables[Tables.properties]["Type"].to_list())
    defined_classes = set(tables[Tables.classes]["Class"].to_list())

    rows = []
    for class_ in referred_types.difference(defined_classes).difference(xsd_types):
        rows += [
            {
                "Class": class_,
                "Name": None,
                "Description": None,
                "Parent Class": None,
                "Deprecated": False,
                "Deprecation Date": None,
                "Replaced By": None,
                "Source": None,
                "Source Entity Name": None,
                "Match Type": None,
                "Comment": (
                    "Added by NEAT. "
                    "This is a class that a domain of a property but was not defined in the ontology. "
                    "It is added by NEAT to make the ontology compliant with CDF."
                ),
            }
        ]

    if rows:
        tables[Tables.classes] = pd.concat(
            [tables[Tables.classes], pd.DataFrame(rows)],
            ignore_index=True,
        )

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
        properties_to_add = ["label"]
    undefined_classes = set(tables[Tables.classes].Class.to_list()) - set(tables[Tables.properties].Class.to_list())

    rows = []
    for class_ in undefined_classes:
        for property_ in properties_to_add:
            rows += [
                {
                    "Class": class_,
                    "Property": property_,
                    "Name": property_,
                    "Description": None,
                    "Type": "string",
                    "Min Count": None,
                    "Max Count": 1,
                    "Deprecated": False,
                    "Deprecation Date": None,
                    "Replaced By": None,
                    "Source": None,
                    "Source Entity Name": None,
                    "Match Type": None,
                    "Comment": "Added by NEAT. Default property to make the ontology compliant with CDF.",
                }
            ]

    if rows:
        tables[Tables.properties] = pd.concat(
            [tables[Tables.properties], pd.DataFrame(rows)],
            ignore_index=True,
        )

    return tables


def _add_entity_type_property(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    missing_entity_type = set(
        tables[Tables.properties].groupby("Class").filter(lambda x: "entityType" not in x.Property.to_list()).Class
    )

    rows = []
    for class_ in missing_entity_type:
        rows += [
            {
                "Class": class_,
                "Property": "entityType",
                "Name": "entityType",
                "Description": None,
                "Type": "string",
                "Min Count": None,
                "Max Count": 1,
                "Deprecated": False,
                "Deprecation Date": None,
                "Replaced By": None,
                "Source": None,
                "Source Entity Name": None,
                "Match Type": None,
                "Comment": "Added by NEAT. Default property added to make the ontology compliant with CDF.",
            }
        ]

    if rows:
        tables[Tables.properties] = pd.concat(
            [tables[Tables.properties], pd.DataFrame(rows)],
            ignore_index=True,
        )
    return tables
