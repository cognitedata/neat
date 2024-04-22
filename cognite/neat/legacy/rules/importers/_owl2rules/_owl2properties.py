from typing import cast

import numpy as np
import pandas as pd
from rdflib import Graph

from cognite.neat.utils.utils import remove_namespace

from ._owl2classes import _data_type_property_class, _object_property_class, _thing_class


def parse_owl_properties(graph: Graph, make_compliant: bool = False, language: str = "en") -> pd.DataFrame:
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

    query = """

    SELECT ?class ?property ?name ?description ?type ?minCount ?maxCount
     ?deprecated ?deprecationDate ?replacedBy ?source ?sourceEntity
     ?match ?comment ?propertyType
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
        FILTER (!bound(?type) || !isBlank(?type))
        FILTER (!bound(?class) || !isBlank(?class))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        OPTIONAL {?property owl:deprecated ?deprecated} .
    }
    """

    raw_df = _parse_raw_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return pd.concat([raw_df, pd.DataFrame([len(raw_df) * [""]])], ignore_index=True)

    # group values and clean up
    processed_df = _clean_up_properties(raw_df)

    # make compliant
    if make_compliant:
        processed_df = make_properties_compliant(processed_df)

    # drop column _property_type, which was a helper column:
    processed_df.drop(columns=["_property_type"], inplace=True)

    return processed_df


def _parse_raw_dataframe(query_results: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(
        query_results,
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
            "_property_type",
        ],
    )
    if df.empty:
        return df

    df.replace(np.nan, "", regex=True, inplace=True)

    df.Source = df.Property
    df.Class = df.Class.apply(lambda x: remove_namespace(x))
    df.Property = df.Property.apply(lambda x: remove_namespace(x))
    df.Type = df.Type.apply(lambda x: remove_namespace(x))
    df["Source Entity Name"] = df.Property
    df["Match Type"] = len(df) * ["exact"]
    df["_property_type"] = df["_property_type"].apply(lambda x: remove_namespace(x))

    return df


def _clean_up_properties(df: pd.DataFrame) -> pd.DataFrame:
    class_grouped_dfs = df.groupby("Class")

    clean_list = []

    for class_, class_grouped_df in class_grouped_dfs:
        property_grouped_dfs = class_grouped_df.groupby("Property")
        for property_, property_grouped_df in property_grouped_dfs:
            clean_list += [
                {
                    "Class": class_,
                    "Property": property_,
                    "Name": property_grouped_df["Name"].unique()[0],
                    "Description": "\n".join(list(property_grouped_df.Description.unique()))[:1024],
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
                    "_property_type": property_grouped_df["_property_type"].unique()[0],
                }
            ]

    df = pd.DataFrame(clean_list)
    df.replace("", None, inplace=True)

    return df


def make_properties_compliant(properties: pd.DataFrame) -> pd.DataFrame:
    # default to None if "Min Count" is not specified
    properties["Min Count"] = properties["Min Count"].apply(lambda x: None if not isinstance(x, int) or x == "" else x)

    # default to None if "Max Count" is not specified
    properties["Max Count"] = properties["Max Count"].apply(lambda x: 1 if not isinstance(x, int) or x == "" else x)

    # Replace empty or non-string values in "Match Type" column with "exact"
    properties["Match Type"] = properties["Match Type"].fillna("exact")
    properties["Match Type"] = properties["Match Type"].apply(
        lambda x: "exact" if not isinstance(x, str) or len(x) == 0 else x
    )

    # Replace empty or non-string values in "Comment" column with a default value
    properties["Comment"] = properties["Comment"].fillna("Imported from Ontology by NEAT")
    properties["Comment"] = properties["Comment"].apply(
        lambda x: "Imported from Ontology by NEAT" if not isinstance(x, str) or len(x) == 0 else x
    )

    # Replace empty or non-boolean values in "Deprecated" column with False
    properties["Deprecated"] = properties["Deprecated"].fillna(False)
    properties["Deprecated"] = properties["Deprecated"].apply(lambda x: False if not isinstance(x, bool) else x)

    # Reduce length of elements in the "Description" column to 1024 characters
    properties["Description"] = properties["Description"].apply(lambda x: x[:1024] if isinstance(x, str) else None)

    # fixes and additions
    properties = fix_dangling_properties(properties)
    properties = fix_missing_property_value_type(properties)

    return properties


def fix_dangling_properties(properties: pd.DataFrame) -> pd.DataFrame:
    """This method fixes properties which are missing a domain definition in the ontology.

    Args:
        properties: Dataframe containing properties

    Returns:
        Dataframe containing properties with fixed domain
    """
    domain = {
        "ObjectProperty": _object_property_class()["Class"],
        "DatatypeProperty": _data_type_property_class()["Class"],
    }

    # apply missing range
    properties["Class"] = properties.apply(
        lambda row: domain[row._property_type]
        if row._property_type == "ObjectProperty" and pd.isna(row["Class"])
        else domain["DatatypeProperty"]
        if pd.isna(row["Class"])
        else row["Class"],
        axis=1,
    )
    return properties


def fix_missing_property_value_type(properties: pd.DataFrame) -> pd.DataFrame:
    """This method fixes properties which are missing a range definition in the ontology.

    Args:
        properties: Dataframe containing properties

    Returns:
        Dataframe containing properties with fixed range
    """
    # apply missing range
    properties["Type"] = properties.apply(
        lambda row: _thing_class()["Class"]
        if row._property_type == "ObjectProperty" and pd.isna(row["Type"])
        else "string"
        if pd.isna(row["Type"])
        else row["Type"],
        axis=1,
    )

    return properties
