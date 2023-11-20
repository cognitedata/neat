import numpy as np
import pandas as pd
from rdflib import Graph

from cognite.neat.utils.utils import remove_namespace


def parse_owl_properties(graph: Graph, make_compliant: bool = False) -> pd.DataFrame:
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

    if make_compliant:
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

    if make_compliant:
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
