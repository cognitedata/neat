from typing import cast

import numpy as np
import pandas as pd
from rdflib import OWL, Graph

from cognite.neat.rules.models._base import MatchType
from cognite.neat.utils.utils import remove_namespace_from_uri


def parse_imf_to_classes(graph: Graph, language: str = "en") -> list[dict]:
    """Parse IMF elements from RDF-graph and extract classes to pandas dataframe.

    Args:
        graph: Graph containing imf elements
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing imf elements

    !!! note "IMF Compliance"
        The IMF elements are expressed in RDF, primarily using SHACL and OWL. To ensure
        that the resulting classes are compliant with CDF, similar validation checks as
        in the OWL ontology importer are applied.

        For the IMF-types more of the compliance logic is placed directly in the SPARQL
        query. Among these are the creation of class name not starting with a number,
        and ensuring that all classes have a parent.

        IMF-attributes are considered both classes and properties. This kind of punning
        is necessary to capture additional information carried by attributes. They carry,
        among other things, a set of relationsships to reference terms, units of measure,
        and qualifiers that together make up the meaning of the attribute.
    """

    query = """
    SELECT ?class ?name ?description ?parentClass ?reference ?match ?comment
    WHERE {
        #Finding IMF - elements
        VALUES ?type { imf:BlockType imf:TerminalType imf:AttributeType }
        ?imfClass a ?type .
        OPTIONAL {?imfClass rdfs:subClassOf ?parent }.
        OPTIONAL {?imfClass rdfs:label | skos:prefLabel ?name }.
        OPTIONAL {?imfClass rdfs:comment | skos:description ?description} .

        # Finding the last segment of the class IRI
        BIND(STR(?imfClass) AS ?classString)
        BIND(REPLACE(?classString, "^.*[/#]([^/#]*)$", "$1") AS ?classSegment)
        BIND(IF(CONTAINS(?classString, "imf/"), CONCAT("IMF_", ?classSegment) , ?classSegment) AS ?class)

        # Add imf:Attribute as parent class
        BIND(IF(!bound(?parent) && ?type = imf:AttributeType, imf:Attribute, ?parent) AS ?parentClass)

        # Rebind the IRI of the IMF-type to the ?reference variable to align with dataframe column headers
        # This is solely for readability, the ?imfClass could have been returnered directly instead of ?reference
        BIND(?imfClass AS ?reference)

        FILTER (!isBlank(?class))
        FILTER (!bound(?parentClass) || !isBlank(?parentClass))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
    }
    """

    # create raw dataframe
    raw_df = _parse_raw_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return []

    # group values and clean up
    processed_df = _clean_up_classes(raw_df)

    # make compliant
    processed_df = make_classes_compliant(processed_df)

    # Make Parent Class list elements into string joined with comma
    processed_df["Parent Class"] = processed_df["Parent Class"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) and x else None
    )

    return processed_df.dropna(axis=0, how="all").replace(float("nan"), None).to_dict(orient="records")


def _parse_raw_dataframe(query_results: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(
        query_results,
        columns=["Class", "Name", "Description", "Parent Class", "Reference", "Match", "Comment"],
    )
    if df.empty:
        return df

    # # remove NaNs
    df.replace(np.nan, "", regex=True, inplace=True)

    df["Reference"] = df.Reference
    df["Class"] = df.Class
    df["Match Type"] = len(df) * [MatchType.exact]
    df["Comment"] = len(df) * [None]
    df["Parent Class"] = df["Parent Class"].apply(lambda x: remove_namespace_from_uri(x))

    return df


def _clean_up_classes(df: pd.DataFrame) -> pd.DataFrame:
    clean_list = [
        {
            "Class": class_,
            "Name": group_df["Name"].unique()[0],
            "Description": "\n".join(list(group_df["Description"].unique())),
            "Parent Class": ", ".join(list(group_df["Parent Class"].unique())),
            "Reference": group_df["Reference"].unique()[0],
            "Match Type": group_df["Match Type"].unique()[0],
            "Comment": group_df["Comment"].unique()[0],
        }
        for class_, group_df in df.groupby("Class")
    ]

    df = pd.DataFrame(clean_list)

    # bring NaNs back
    df.replace("", None, inplace=True)

    # split Parent Class column back into list
    df["Parent Class"] = df["Parent Class"].apply(lambda x: x.split(", ") if isinstance(x, str) else None)

    return df


def make_classes_compliant(classes: pd.DataFrame) -> pd.DataFrame:
    """Make classes compliant.

    Returns:
        Dataframe containing compliant classes

    !!! note "About the compliant classes"
        The compliant classes are based on the OWL base ontology, but adapted to NEAT and use in CDF.
        One thing to note is that this method would not be able to fix issues with class ids which
        are not compliant with the CDF naming convention. For example, if a class id contains a space,
        starts with a number, etc. This will cause issues when trying to create the class in CDF.
    """

    # Replace empty or non-string values in "Match" column with "exact"
    classes["Match Type"] = classes["Match Type"].fillna(MatchType.exact)
    classes["Match Type"] = classes["Match Type"].apply(
        lambda x: MatchType.exact if not isinstance(x, str) or len(x) == 0 else x
    )

    # Replace empty or non-string values in "Comment" column with a default value
    classes["Comment"] = classes["Comment"].fillna("Imported from IMF type by NEAT")
    classes["Comment"] = classes["Comment"].apply(
        lambda x: "Imported from IMF by NEAT" if not isinstance(x, str) or len(x) == 0 else x
    )

    # Add _object_property_class, _data_type_property_class, _thing_class to the dataframe
    classes = pd.concat(
        [classes, pd.DataFrame([_object_property_class(), _data_type_property_class(), _thing_class()])],
        ignore_index=True,
    )

    # Reduce length of elements in the "Description" column to 1024 characters
    classes["Description"] = classes["Description"].apply(lambda x: x[:1024] if isinstance(x, str) else None)

    # Add missing parent classes to the dataframe
    classes = pd.concat(
        [classes, pd.DataFrame(_add_parent_class(classes))],
        ignore_index=True,
    )

    return classes


def _object_property_class() -> dict:
    return {
        "Class": "ObjectProperty",
        "Name": None,
        "Description": "The class of object properties.",
        "Parent Class": None,
        "Reference": OWL.ObjectProperty,
        "Match Type": MatchType.exact,
        "Comment": "Added by NEAT based on owl:ObjectProperty but adapted to NEAT and use in CDF.",
    }


def _data_type_property_class() -> dict:
    return {
        "Class": "DatatypeProperty",
        "Name": None,
        "Description": "The class of data properties.",
        "Parent Class": None,
        "Reference": OWL.DatatypeProperty,
        "Match Type": MatchType.exact,
        "Comment": "Added by NEAT based on owl:DatatypeProperty but adapted to NEAT and use in CDF.",
    }


def _thing_class() -> dict:
    return {
        "Class": "Thing",
        "Name": None,
        "Description": "The class of holding class individuals.",
        "Parent Class": None,
        "Reference": OWL.Thing,
        "Match Type": MatchType.exact,
        "Comment": (
            "Added by NEAT. "
            "Imported from OWL base ontology, it is meant for use as a default"
            " value type for object properties which miss a declared range."
        ),
    }


def _add_parent_class(df: pd.DataFrame) -> list[dict]:
    parent_set = {
        item
        for sublist in df["Parent Class"].tolist()
        if sublist
        for item in sublist
        if item != "" and item is not None
    }
    class_set = set(df["Class"].tolist())

    rows = []
    for missing_parent_class in parent_set.difference(class_set):
        rows += [
            {
                "Class": missing_parent_class,
                "Name": None,
                "Description": None,
                "Parent Class": None,
                "Reference": None,
                "Match Type": None,
                "Comment": (
                    "Added by NEAT. "
                    "This is a parent class that is missing in the ontology. "
                    "It is added by NEAT to make the ontology compliant with CDF."
                ),
            }
        ]

    return rows
