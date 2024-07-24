from typing import cast

import numpy as np
import pandas as pd
from rdflib import Graph, Literal

from cognite.neat.rules.models._base import MatchType
from cognite.neat.utils.utils import remove_namespace_from_uri

from ._imf2classes import _data_type_property_class, _object_property_class, _thing_class


def parse_imf_to_properties(graph: Graph, language: str = "en") -> list[dict]:
    """Parse IMF elements from RDF-graph and extract properties to pandas dataframe.

    Args:
        graph: Graph containing imf elements
        language: Language to use for parsing, by default "en"

    Returns:
        List of dictionaries containing properties extracted from IMF elements

    !!! note "IMF Compliance"
        The IMF elements are expressed in RDF, primarily using SHACL and OWL. To ensure
        that the resulting properties are compliant with CDF, similar validation checks
        as in the OWL ontology importer are applied.

        For the IMF-types more of the compliance logic is placed directly in the SPARQL
        query. Among these are the creation of class and property names not starting
        with a number, ensuring property types as well as default cardinality boundraries.

        IMF-attributes are considered both classes and properties. This kind of punning
        is necessary to capture additional information carried by attributes. They carry,
        among other things, a set of relationsships to reference terms, units of measure,
        and qualifiers that together make up the meaning of the attribute. These references
        are listed as additional properties with default values.
    """

    query = """
    SELECT ?class ?property ?name ?description ?valueType ?minCount ?maxCount ?default ?reference
    ?match ?comment ?propertyType
    WHERE
    {
        # Finding IMF-blocks and terminals
        {
            VALUES ?classType { imf:BlockType imf:TerminalType }
            ?imfClass a ?classType ;
                sh:property ?propertyShape .
                ?propertyShape sh:path ?imfProperty .

            OPTIONAL { ?imfProperty skos:prefLabel ?name . }
            OPTIONAL { ?imfProperty skos:description ?description . }
            OPTIONAL { ?imfProperty rdfs:range ?range . }
            OPTIONAL { ?imfProperty a ?type . }
            OPTIONAL { ?propertyShape sh:minCount ?minCardinality} .
            OPTIONAL { ?propertyShape sh:maxCount ?maxCardinality} .
            OPTIONAL { ?propertyShape sh:hasValue ?defualt . }
            OPTIONAL { ?propertyShape sh:class | sh:qualifiedValueShape/sh:class ?valueShape .}
        }
        UNION
        # Finding the IMF-attribute types
        {
            ?imfClass a imf:AttributeType ;
                ?imfProperty ?default .

            # imf:predicate is required
            BIND(IF(?imfProperty = <http://ns.imfid.org/imf#predicate>, 1, 0) AS ?minCardinality)

            # The following information is used to describe the attribute when it is connected to a block or a terminal
            # and not duplicated here.
            FILTER(?imfProperty != rdf:type && ?imfProperty != skos:prefLabel && ?imfProperty != skos:description)
        }

        # Finding the last segment of the class IRI
        BIND(STR(?imfClass) AS ?classString)
        BIND(REPLACE(?classString, "^.*[/#]([^/#]*)$", "$1") AS ?classSegment)
        BIND(IF(CONTAINS(?classString, "imf/"), CONCAT("IMF_", ?classSegment) , ?classSegment) AS ?class)

        # Finding the last segment of the property IRI
        BIND(STR(?imfProperty) AS ?propertyString)
        BIND(REPLACE(?propertyString, "^.*[/#]([^/#]*)$", "$1") AS ?propertySegment)
        BIND(IF(CONTAINS(?propertyString, "imf/"), CONCAT("IMF_", ?propertySegment) , ?propertySegment) AS ?property)

        # Set the value type for the property based on sh:class, sh:qualifiedValueType or rdfs:range
        BIND(IF(BOUND(?valueShape), ?valueShape, IF(BOUND(?range) , ?range , ?valueShape)) AS ?valueIriType)

        # Finding the last segment of value types
        BIND(STR(?valueIriType) AS ?valueTypeString)
        BIND(REPLACE(?valueTypeString, "^.*[/#]([^/#]*)$", "$1") AS ?valueTypeSegment)
        BIND(IF(CONTAINS(?valueTypeString, "imf/"), CONCAT("IMF_", ?valueTypeSegment) , ?valueTypeSegment)
            AS ?valueType)

        # Helper variable to set property type if value type is not already set.
        BIND(IF(BOUND(?type) && ?type = owl:DatatypeProperty, ?type , owl:ObjectProperty) AS ?propertyType)

        # Assert cardinality values if they do not exist
        BIND(IF(BOUND(?minCardinality), ?minCardinality, 0) AS ?minCount)
        BIND(IF(BOUND(?maxCardinality), ?maxCardinality, 1) AS ?maxCount)

        # Rebind the IRI of the IMF-attribute to the ?reference variable to align with dataframe column headers
        # This is solely for readability, the ?imfClass could have been returnered directly instead of ?reference
        BIND(?imfProperty AS ?reference)

        FILTER (!isBlank(?property))
        FILTER (!bound(?class) || !isBlank(?class))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
    }
    """

    raw_df = _parse_raw_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return []

    # group values and clean up
    processed_df = _clean_up_properties(raw_df)

    # make compliant
    processed_df = make_properties_compliant(processed_df)

    # drop column _property_type, which was a helper column:
    processed_df.drop(columns=["_property_type"], inplace=True)

    return processed_df.to_dict(orient="records")


def _parse_raw_dataframe(query_results: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(
        query_results,
        columns=[
            "Class",
            "Property",
            "Name",
            "Description",
            "Value Type",
            "Min Count",
            "Max Count",
            "Default",
            "Reference",
            "Match Type",
            "Comment",
            "_property_type",
        ],
    )
    if df.empty:
        return df

    df.replace(np.nan, "", regex=True, inplace=True)

    df["Match Type"] = len(df) * [MatchType.exact]
    df["Comment"] = len(df) * [None]
    df["_property_type"] = df["_property_type"].apply(lambda x: remove_namespace_from_uri(x))

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
                    "Description": "\n".join(list(property_grouped_df["Description"].unique()))[:1024],
                    "Value Type": property_grouped_df["Value Type"].unique()[0],
                    "Min Count": property_grouped_df["Min Count"].unique()[0],
                    "Max Count": property_grouped_df["Max Count"].unique()[0],
                    "Default": property_grouped_df["Default"].unique()[0],
                    "Reference": property_grouped_df["Reference"].unique()[0],
                    "Match Type": property_grouped_df["Match Type"].unique()[0],
                    "Comment": property_grouped_df["Comment"].unique()[0],
                    "_property_type": property_grouped_df["_property_type"].unique()[0],
                }
            ]

    df = pd.DataFrame(clean_list)
    df.replace("", None, inplace=True)

    return df


def make_properties_compliant(properties: pd.DataFrame) -> pd.DataFrame:
    # default to 0 if "Min Count" is not specified
    properties["Min Count"] = properties["Min Count"].apply(lambda x: 0 if not isinstance(x, Literal) or x == "" else x)

    # default to 1 if "Max Count" is not specified
    properties["Max Count"] = properties["Max Count"].apply(lambda x: 1 if not isinstance(x, Literal) or x == "" else x)

    # Replace empty or non-string values in "Match Type" column with "exact"
    properties["Match Type"] = properties["Match Type"].fillna("exact")
    properties["Match Type"] = properties["Match Type"].apply(
        lambda x: "exact" if not isinstance(x, str) or len(x) == 0 else x
    )

    # Replace empty or non-string values in "Comment" column with a default value
    properties["Comment"] = properties["Comment"].fillna("Imported from IMF type by NEAT")
    properties["Comment"] = properties["Comment"].apply(
        lambda x: "Imported from Ontology by NEAT" if not isinstance(x, str) or len(x) == 0 else x
    )

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
        lambda row: (
            domain[row._property_type]
            if row._property_type == "ObjectProperty" and pd.isna(row["Class"])
            else domain["DatatypeProperty"]
            if pd.isna(row["Class"])
            else row["Class"]
        ),
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
    properties["Value Type"] = properties.apply(
        lambda row: (
            _thing_class()["Class"]
            if row._property_type == "ObjectProperty" and pd.isna(row["Value Type"])
            else "string"
            if pd.isna(row["Value Type"])
            else row["Value Type"]
        ),
        axis=1,
    )

    return properties
