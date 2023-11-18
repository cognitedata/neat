"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

from pathlib import Path

import numpy as np
import pandas as pd
from rdflib import DC, DCTERMS, OWL, RDF, RDFS, SKOS, Graph, Namespace

from cognite.neat.rules.importer._base import BaseImporter
from cognite.neat.rules.models.tables import Tables
from cognite.neat.utils.utils import get_namespace, remove_namespace


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

    def to_tables(self, use_default_values: bool = False) -> dict[str, pd.DataFrame]:
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
            Tables.metadata: _parse_owl_metadata_df(graph, use_default_values=use_default_values),
            Tables.classes: _parse_owl_classes_df(graph, use_default_values=use_default_values),
            Tables.properties: _parse_owl_properties_df(graph, use_default_values=use_default_values),
        }


def _parse_owl_metadata_df(graph: Graph, use_default_values: bool = False) -> pd.DataFrame:
    """Parse owl metadata from graph to pandas dataframe.

    Args:
        graph: Graph containing owl metadata
        use_default_values: Flag for setting default values for missing metadata, by default False

    Returns:
        Dataframe containing owl metadata

    """

    if use_default_values:
        query = (
            'SELECT ?namespace (COALESCE(?prefix, "neat") AS ?prefix)'
            ' (COALESCE(?dataModelName, "neat") AS ?dataModelName)'
            ' (COALESCE(?cdfSpaceName, "playground") AS ?cdfSpaceName)'
            ' (COALESCE(?version, "1.0.0") AS ?version)'
            ' (COALESCE(?isCurrentVersion, "True"^^xsd:boolean) AS ?isCurrentVersion)'
            ' (COALESCE(?created, "1983-01-22T02:00:00Z"^^xsd:dateTime) AS ?created)'
            ' (COALESCE(?updated, "2021-11-13T00:00:00Z"^^xsd:dateTime) AS ?updated)'
            ' (COALESCE(?title, "OWL Inferred Data Model") AS ?title)'
            ' (COALESCE(?description, "This data model has been inferred with NEAT") AS ?description)'
            ' (COALESCE(?creator, "NEAT") AS ?creator)'
            ' (COALESCE(?contributor, "NEAT") AS ?contributor)'
            ' (COALESCE(?rights, "Unknown rights of usage") AS ?rights)'
            ' (COALESCE(?license, "Unknown license") AS ?license)'
        )
    else:
        query = (
            "SELECT ?namespace ?prefix ?dataModelName ?cdfSpaceName ?version ?isCurrentVersion "
            "?created ?updated ?title ?description ?creator ?contributor ?rights ?license"
        )

    query += """
    WHERE {
        ?namespace a owl:Ontology .
        OPTIONAL {?namespace owl:versionInfo ?version }.
        OPTIONAL {?namespace dcterms:creator ?creator }.
        OPTIONAL {?namespace dcterms:title|rdfs:label|skos:prefLabel ?title }.
        OPTIONAL {?namespace dcterms:contributor ?contributor }.
        OPTIONAL {?namespace dcterms:modified ?updated }.
        OPTIONAL {?namespace dcterms:created ?created }.
        OPTIONAL {?namespace dcterms:description ?description }.

        OPTIONAL {?namespace dcterms:rights|dc:rights ?rights }.

        OPTIONAL {?namespace dcterms:license|dc:license ?license }.
        FILTER (!isBlank(?namespace))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        FILTER (!bound(?title) || LANG(?title) = "" || LANGMATCHES(LANG(?title), "en"))
    }
    """

    results = [{item if item is not None else "" for item in sublist} for sublist in list(zip(*graph.query(query)))]

    clean_list = {
        "namespace": Namespace(results[0].pop()),
        "prefix": results[1].pop(),
        "dataModelName": results[2].pop(),
        "cdfSpaceName": results[3].pop(),
        "version": results[4].pop(),
        "isCurrentVersion": results[5].pop(),
        "created": results[6].pop(),
        "updated": results[7].pop(),
        "title": results[8].pop(),
        "description": results[9].pop(),
        "creator": ", ".join(results[10]),
        "contributor": ", ".join(results[11]),
        "rights": results[12].pop(),
        "license": results[13].pop(),
    }

    return pd.DataFrame(list(clean_list.items()), columns=["Key", "Value"])


def _parse_owl_classes_df(graph: Graph, use_default_values: bool = False) -> pd.DataFrame:
    """Get all classes from the graph and their parent classes.

    Parameters
    ----------
    graph : Graph
        Graph to query
    parsing_config : dict, optional
        Configuration for parsing the dataframe, by default None

    Returns
    -------
    pd.DataFrame
        Dataframe with columns: class, parentClass
    """
    if use_default_values:
        query = (
            "SELECT ?class ?name ?description ?parentClass"
            ' (COALESCE(?deprecated, "False"^^xsd:boolean) AS ?deprecated)'
            " ?deprecationDate ?replacedBy ?source ?sourceEntity ?match"
            ' (COALESCE(?comment, "Extracted using NEAT") AS ?comment)'
        )
    else:
        query = (
            "SELECT ?class ?name ?description ?parentClass ?deprecated ?deprecationDate"
            " ?replacedBy ?source ?sourceEntity ?match ?comment"
        )

    query += """
        WHERE {
        ?class a owl:Class .
        OPTIONAL {?class rdfs:subClassOf ?parentClass }.
        OPTIONAL {?class rdfs:label ?name }.
        OPTIONAL {?class rdfs:comment ?description} .
        OPTIONAL {?class owl:deprecated ?deprecated} .
        FILTER (!isBlank(?class))
        FILTER (!bound(?parentClass) || !isBlank(?parentClass))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
    }
    """

    raw_df = pd.DataFrame(
        list(graph.query(query)),
        columns=[
            "Class",
            "Name",
            "Description",
            "Parent Class",
            "Deprecated",
            "Deprecation Date",
            "Replaced By",
            "Source",
            "Source Entity Name",
            "Match",
            "Comment",
        ],
    )
    if raw_df.empty:
        raw_df = pd.concat([raw_df, pd.DataFrame([len(raw_df) * [""]])], ignore_index=True)
        return raw_df
    raw_df.replace(np.nan, "", regex=True, inplace=True)

    raw_df.Source = raw_df.Class
    raw_df.Class = raw_df.Class.apply(lambda x: remove_namespace(x))
    raw_df["Source Entity Name"] = raw_df.Class
    raw_df["Match"] = len(raw_df) * ["exact"]
    raw_df["Parent Class"] = raw_df["Parent Class"].apply(lambda x: remove_namespace(x))

    grouped_df = raw_df.groupby("Class")

    clean_list = [
        {
            "Class": class_,
            "Name": group_df["Name"].unique()[0],
            "Description": "\n".join(list(group_df.Description.unique()))[:1028],
            "Parent Class": ", ".join(list(group_df["Parent Class"].unique())),
            "Deprecated": group_df.Deprecated.unique()[0],
            "Deprecation Date": group_df["Deprecation Date"].unique()[0],
            "Replaced By": group_df["Replaced By"].unique()[0],
            "Source": group_df["Source"].unique()[0],
            "Source Entity Name": group_df["Name"].unique()[0]
            if group_df["Name"].unique()[0]
            else group_df["Source Entity Name"].unique()[0],
            "Match Type": group_df["Match"].unique()[0],
            "Comment": group_df["Comment"].unique()[0],
        }
        for class_, group_df in grouped_df
    ]

    df = pd.DataFrame(clean_list)
    df.replace("", None, inplace=True)

    if use_default_values:
        df = pd.concat(
            [df, pd.DataFrame([_object_property_class(), _data_type_property_class(), _thing_class()])],
            ignore_index=True,
        )

    return df


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
