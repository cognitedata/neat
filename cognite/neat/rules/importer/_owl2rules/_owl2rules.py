"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

from pathlib import Path

import numpy as np
import pandas as pd
from pydantic_core import ErrorDetails
from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph

from cognite.neat.rules.importer._base import BaseImporter
from cognite.neat.rules.models.raw_rules import RawRules
from cognite.neat.rules.models.rules import Rules
from cognite.neat.rules.models.tables import Tables
from cognite.neat.utils.utils import remove_namespace

from ._classes import parse_owl_classes
from ._metadata import parse_owl_metadata


class OWLImporter(BaseImporter):
    """Convert OWL ontology to tables/ transformation rules / Excel file.

        Args:
            owl_filepath: Path to OWL ontology

    !!! Note
        OWL Ontologies typically lacks some information that is required for making a complete
        data model. This means that the methods .to_rules() will typically fail. Instead, it is recommended
        that you use the .to_spreadsheet() method to generate an Excel file, and then manually add the missing
        information to the Excel file. The Excel file can then be converted to a TransformationRules object.

        One can set the `use_default_values` parameter to True to allow neat to set default
        values for missing information.

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

        return {
            Tables.metadata: parse_owl_metadata(graph, make_compliant=make_compliant),
            Tables.classes: parse_owl_classes(graph, make_compliant=make_compliant),
            Tables.properties: _parse_owl_properties_df(graph, use_default_values=make_compliant),
        }

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

    # needs reimplementation of base methods...


def _parse_owl_properties_df(graph: Graph, use_default_values: bool = False) -> pd.DataFrame:
    """Get all properties from the OWL ontology

    Parameters
    ----------
    graph : Graph
        Graph to query
    parsing_config : dict, optional
        Configuration for parsing the dataframe, by default None

    Returns
    -------
    pd.DataFrame
        Dataframe with columns: class, property, name, ...
    """

    if use_default_values:
        query = (
            "SELECT ?class ?property ?name ?description ?type ?minCount"
            ' (COALESCE(?maxCount, "1") AS ?maxCount)'
            ' (COALESCE(?deprecated, "False"^^xsd:boolean) AS ?deprecated)'
            " ?deprecationDate ?replacedBy ?source ?sourceEntity ?match"
            ' (COALESCE(?comment, "Extracted using NEAT") AS ?comment) ?propertyType'
        )
        print("Using default values")
    else:
        print("Not default values")
        query = (
            "SELECT ?class ?property ?name ?description ?type ?minCount ?maxCount"
            " ?deprecated ?deprecationDate ?replacedBy ?source ?sourceEntity"
            " ?match ?comment ?propertyType"
        )

    query += """
    WHERE {
        ?property a ?propertyType.
        FILTER (?propertyType IN (owl:ObjectProperty, owl:DatatypeProperty ) )
        OPTIONAL {?property rdfs:domain ?class }.
        OPTIONAL {?property rdfs:range ?type }.
        OPTIONAL {?property rdfs:label ?name }.
        OPTIONAL {?property rdfs:comment ?description} .
        OPTIONAL {?property owl:maxCardinality ?maxCount} .
        OPTIONAL {?property owl:minCardinality ?minCount} .
        FILTER (!isBlank(?property))
        FILTER (!isBlank(?type))
        FILTER (!bound(?class) || !isBlank(?class))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        OPTIONAL {?property owl:deprecated ?deprecated} .
    }
    """

    raw_df = pd.DataFrame(
        list(graph.query(query)),
        columns=[
            "Class",
            "Property",
            "Name",
            "Description",
            "Type",
            "Min Count",
            "Max Count",
            "Deprecated",
            "Deprecation Date",
            "Replaced By",
            "Source",
            "Source Entity Name",
            "Match Type",
            "Comment",
            "Property Type",
        ],
    )
    if raw_df.empty:
        return raw_df
    raw_df.replace(np.nan, "", regex=True, inplace=True)

    raw_df.Source = raw_df.Property
    raw_df.Class = raw_df.Class.apply(lambda x: remove_namespace(x))
    raw_df.Property = raw_df.Property.apply(lambda x: remove_namespace(x))
    raw_df.Type = raw_df.Type.apply(lambda x: remove_namespace(x))
    raw_df["Source Entity Name"] = raw_df.Property
    raw_df["Match Type"] = len(raw_df) * ["exact"]

    raw_df.replace("", None, inplace=True)

    raw_df["Property Type"] = raw_df["Property Type"].apply(lambda x: remove_namespace(x))

    if use_default_values:
        raw_df["Class"] = raw_df["Class"].fillna(raw_df["Property Type"])
        raw_df["Type"] = raw_df.apply(
            lambda row: "Thing"
            if row["Property Type"] == "ObjectProperty" and pd.isna(row["Type"])
            else "string"
            if pd.isna(row["Type"])
            else row["Type"],
            axis=1,
        )

    raw_df.drop("Property Type", axis=1, inplace=True)
    raw_df.fillna("", inplace=True)

    class_grouped_dfs = raw_df.groupby("Class")

    clean_list = []

    for class_, class_grouped_df in class_grouped_dfs:
        property_grouped_dfs = class_grouped_df.groupby("Property")
        for property_, property_grouped_df in property_grouped_dfs:
            clean_list += [
                {
                    "Class": class_,
                    "Property": property_,
                    "Name": property_grouped_df["Name"].unique()[0],
                    "Description": "\n".join(list(property_grouped_df.Description.unique()))[:1028],
                    "Type": property_grouped_df.Type.unique()[0],
                    "Min Count": property_grouped_df["Min Count"].unique()[0],
                    "Max Count": property_grouped_df["Max Count"].unique()[0],
                    "Deprecated": property_grouped_df.Deprecated.unique()[0],
                    "Deprecation Date": property_grouped_df["Deprecation Date"].unique()[0],
                    "Replaced By": property_grouped_df["Replaced By"].unique()[0],
                    "Source": property_grouped_df["Source"].unique()[0],
                    "Source Entity Name": property_grouped_df["Source Entity Name"].unique()[0],
                    "Match Type": property_grouped_df["Match Type"].unique()[0],
                    "Comment": property_grouped_df["Comment"].unique()[0],
                }
            ]

    df = pd.DataFrame(clean_list)
    df.replace("", None, inplace=True)

    return df
