from typing import cast

import numpy as np
import pandas as pd
from rdflib import OWL, Graph

from cognite.neat.utils.utils import remove_namespace


def parse_owl_classes(graph: Graph, make_compliant: bool = False, language: str = "en") -> pd.DataFrame:
    """Parse owl classes from graph to pandas dataframe.

    Args:
        graph: Graph containing owl classes
        make_compliant: Flag for generating compliant classes, by default False
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing owl classes

    !!! note "make_compliant"
        If `make_compliant` is set to True, in presence of errors, default values will be used instead.
        This makes the method very opinionated, but results in a compliant classes.
    """

    query = """
        SELECT ?class ?name ?description ?parentClass ?deprecated ?deprecationDate
        ?replacedBy ?source ?sourceEntity ?match ?comment
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

    # create raw dataframe

    raw_df = _parse_raw_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return pd.concat([raw_df, pd.DataFrame([len(raw_df) * [""]])], ignore_index=True)

    # group values and clean up
    processed_df = _clean_up_classes(raw_df)

    # make compliant
    if make_compliant:
        processed_df = make_classes_compliant(processed_df)

    # Make Parent Class list elements into string joined with comma
    processed_df["Parent Class"] = processed_df["Parent Class"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) and x else None
    )

    return processed_df


def _parse_raw_dataframe(query_results: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(
        query_results,
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
    if df.empty:
        return df

    # # remove NaNs
    df.replace(np.nan, "", regex=True, inplace=True)

    df.Source = df.Class
    df.Class = df.Class.apply(lambda x: remove_namespace(x))
    df["Source Entity Name"] = df.Class
    df["Match"] = len(df) * ["exact"]
    df["Parent Class"] = df["Parent Class"].apply(lambda x: remove_namespace(x))

    return df


def _clean_up_classes(df: pd.DataFrame) -> pd.DataFrame:
    clean_list = [
        {
            "Class": class_,
            "Name": group_df["Name"].unique()[0],
            "Description": "\n".join(list(group_df.Description.unique())),
            "Parent Class": ", ".join(list(group_df["Parent Class"].unique())),
            "Deprecated": group_df.Deprecated.unique()[0],
            "Deprecation Date": group_df["Deprecation Date"].unique()[0],
            "Replaced By": group_df["Replaced By"].unique()[0],
            "Source": group_df["Source"].unique()[0],
            "Source Entity Name": group_df["Name"].unique()[0],
            "Match Type": group_df["Match"].unique()[0],
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

    # Replace empty or non-string values in "Match Type" column with "exact"
    classes["Match Type"] = classes["Match Type"].fillna("exact")
    classes["Match Type"] = classes["Match Type"].apply(
        lambda x: "exact" if not isinstance(x, str) or len(x) == 0 else x
    )

    # Replace empty or non-string values in "Comment" column with a default value
    classes["Comment"] = classes["Comment"].fillna("Imported from Ontology by NEAT")
    classes["Comment"] = classes["Comment"].apply(
        lambda x: "Imported from Ontology by NEAT" if not isinstance(x, str) or len(x) == 0 else x
    )

    # Replace empty or non-boolean values in "Deprecated" column with False
    classes["Deprecated"] = classes["Deprecated"].fillna(False)
    classes["Deprecated"] = classes["Deprecated"].apply(lambda x: False if not isinstance(x, bool) else x)

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
        "Class": "ObjectPropertyContainer",
        "Name": None,
        "Description": "The class of object properties.",
        "Parent Class": None,
        "Deprecated": False,
        "Deprecation Date": None,
        "Replaced By": None,
        "Source": OWL.ObjectProperty,
        "Source Entity Name": "ObjectProperty",
        "Match Type": "exact",
        "Comment": "Added by NEAT based on owl:ObjectProperty but adapted to NEAT and use in CDF.",
    }


def _data_type_property_class() -> dict:
    return {
        "Class": "DatatypePropertyContainer",
        "Name": None,
        "Description": "The class of data properties.",
        "Parent Class": None,
        "Deprecated": False,
        "Deprecation Date": None,
        "Replaced By": None,
        "Source": OWL.DatatypeProperty,
        "Source Entity Name": "DatatypeProperty",
        "Match Type": "exact",
        "Comment": "Added by NEAT based on owl:DatatypeProperty but adapted to NEAT and use in CDF.",
    }


def _thing_class() -> dict:
    return {
        "Class": "ThingContainer",
        "Name": None,
        "Description": "The class of holding class individuals.",
        "Parent Class": None,
        "Deprecated": False,
        "Deprecation Date": None,
        "Replaced By": None,
        "Source": OWL.Thing,
        "Source Entity Name": "Thing",
        "Match Type": "exact",
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
                "Deprecated": False,
                "Deprecation Date": None,
                "Replaced By": None,
                "Source": None,
                "Source Entity Name": None,
                "Match Type": None,
                "Comment": (
                    "Added by NEAT. "
                    "This is a parent class that is missing in the ontology. "
                    "It is added by NEAT to make the ontology compliant with CDF."
                ),
            }
        ]

    return rows
