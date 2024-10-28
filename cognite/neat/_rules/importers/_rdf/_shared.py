import datetime

import numpy as np
import pandas as pd
from rdflib import OWL, Literal, Namespace

from cognite.neat._rules._constants import PATTERNS
from cognite.neat._rules.models._base_rules import MatchType
from cognite.neat._rules.models.data_types import _XSD_TYPES
from cognite.neat._utils.rdf_ import remove_namespace_from_uri


def parse_raw_classes_dataframe(query_results: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(
        query_results,
        columns=[
            "Class",
            "Name",
            "Description",
            "Parent Class",
            "Reference",
            "Match",
            "Comment",
        ],
    )

    if df.empty:
        return df

    # # remove NaNs
    df.replace(np.nan, "", regex=True, inplace=True)

    df.Class = df.Class.apply(lambda x: remove_namespace_from_uri(x))
    df["Match Type"] = len(df) * [MatchType.exact]
    df["Comment"] = len(df) * [None]
    df["Parent Class"] = df["Parent Class"].apply(lambda x: remove_namespace_from_uri(x))

    return df


def clean_up_classes(df: pd.DataFrame) -> pd.DataFrame:
    clean_list = [
        {
            "Class": class_,
            "Name": group_df["Name"].unique()[0],
            "Description": "\n".join(list(group_df.Description.unique())),
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


def make_classes_compliant(classes: pd.DataFrame, importer: str = "RDF-based") -> pd.DataFrame:
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
    classes["Comment"] = classes["Comment"].fillna(f"Imported using {importer} importer")
    classes["Comment"] = classes["Comment"].apply(
        lambda x: (f"Imported using {importer} importer" if not isinstance(x, str) or len(x) == 0 else x)
    )

    # Add _object_property_class, _data_type_property_class, _thing_class to the dataframe
    classes = pd.concat(
        [
            classes,
            pd.DataFrame([object_property_class(), data_type_property_class(), thing_class()]),
        ],
        ignore_index=True,
    )

    # Reduce length of elements in the "Description" column to 1024 characters
    classes["Description"] = classes["Description"].apply(lambda x: x[:1024] if isinstance(x, str) else None)

    # Add missing parent classes to the dataframe
    classes = pd.concat(
        [classes, pd.DataFrame(add_parent_class(classes))],
        ignore_index=True,
    )

    return classes


def object_property_class() -> dict:
    return {
        "Class": "ObjectProperty",
        "Name": None,
        "Description": "The class of object properties.",
        "Parent Class": None,
        "Reference": OWL.ObjectProperty,
        "Match Type": MatchType.exact,
        "Comment": "Added by NEAT based on owl:ObjectProperty but adapted to NEAT and use in CDF.",
    }


def data_type_property_class() -> dict:
    return {
        "Class": "DatatypeProperty",
        "Name": None,
        "Description": "The class of data properties.",
        "Parent Class": None,
        "Reference": OWL.DatatypeProperty,
        "Match Type": MatchType.exact,
        "Comment": "Added by NEAT based on owl:DatatypeProperty but adapted to NEAT and use in CDF.",
    }


def thing_class() -> dict:
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


def add_parent_class(df: pd.DataFrame) -> list[dict]:
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


def parse_raw_properties_dataframe(query_results: list[tuple]) -> pd.DataFrame:
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

    df.Class = df.Class.apply(lambda x: remove_namespace_from_uri(x))
    df.Property = df.Property.apply(lambda x: remove_namespace_from_uri(x))
    df["Value Type"] = df["Value Type"].apply(lambda x: remove_namespace_from_uri(x))
    df["Match Type"] = len(df) * [MatchType.exact]
    df["Comment"] = len(df) * [None]
    df["_property_type"] = df["_property_type"].apply(lambda x: remove_namespace_from_uri(x))

    return df


def clean_up_properties(df: pd.DataFrame) -> pd.DataFrame:
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


def make_properties_compliant(properties: pd.DataFrame, importer: str = "RDF-based") -> pd.DataFrame:
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
    properties["Comment"] = properties["Comment"].fillna(f"Imported using {importer} importer")
    properties["Comment"] = properties["Comment"].apply(
        lambda x: (f"Imported using {importer} importer" if not isinstance(x, str) or len(x) == 0 else x)
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
        "ObjectProperty": object_property_class()["Class"],
        "DatatypeProperty": data_type_property_class()["Class"],
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
            thing_class()["Class"]
            if row._property_type == "ObjectProperty" and pd.isna(row["Value Type"])
            else "string"
            if pd.isna(row["Value Type"])
            else row["Value Type"]
        ),
        axis=1,
    )

    return properties


def make_metadata_compliant(metadata: dict) -> dict:
    """Attempts to fix errors in metadata, otherwise defaults to values that will pass validation.

    Args:
        metadata: Dictionary containing metadata

    Returns:
        Dictionary containing metadata with fixed errors
    """

    metadata = fix_namespace(metadata, default=Namespace("http://purl.org/cognite/neat#"))
    metadata = fix_prefix(metadata)
    metadata = fix_version(metadata)
    metadata = fix_date(
        metadata,
        date_type="created",
        default=datetime.datetime.now().replace(microsecond=0),
    )
    metadata = fix_date(
        metadata,
        date_type="updated",
        default=datetime.datetime.now().replace(microsecond=0),
    )
    metadata = fix_title(metadata)
    metadata = fix_description(metadata)
    metadata = fix_author(metadata, "creator")
    metadata = fix_rights(metadata)
    metadata = fix_license(metadata)

    return metadata


def fix_license(metadata: dict, default: str = "Unknown license") -> dict:
    if license := metadata.get("license", None):
        if not isinstance(license, str):
            metadata["license"] = default
        elif isinstance(license, str) and len(license) == 0:
            metadata["license"] = default
    else:
        metadata["license"] = default
    return metadata


def fix_rights(metadata: dict, default: str = "Unknown rights") -> dict:
    if rights := metadata.get("rights", None):
        if not isinstance(rights, str):
            metadata["rights"] = default
        elif isinstance(rights, str) and len(rights) == 0:
            metadata["rights"] = default
    else:
        metadata["rights"] = default
    return metadata


def fix_author(metadata: dict, author_type: str = "creator", default: str = "NEAT") -> dict:
    if author := metadata.get(author_type, None):
        if not isinstance(author, str) or isinstance(author, list):
            metadata[author_type] = default
        elif isinstance(author, str) and len(author) == 0:
            metadata[author_type] = default
    else:
        metadata[author_type] = default
    return metadata


def fix_description(metadata: dict, default: str = "This model has been inferred from OWL ontology") -> dict:
    if description := metadata.get("description", None):
        if not isinstance(description, str) or len(description) == 0:
            metadata["description"] = default
        elif isinstance(description, str) and len(description) > 1024:
            metadata["description"] = metadata["description"][:1024]
    else:
        metadata["description"] = default
    return metadata


def fix_prefix(metadata: dict, default: str = "neat") -> dict:
    if prefix := metadata.get("prefix", None):
        if not isinstance(prefix, str) or not PATTERNS.prefix_compliance.match(prefix):
            metadata["prefix"] = default
    else:
        metadata["prefix"] = default
    return metadata


def fix_namespace(metadata: dict, default: Namespace) -> dict:
    if namespace := metadata.get("namespace", None):
        if not isinstance(namespace, Namespace):
            try:
                metadata["namespace"] = Namespace(namespace)
            except Exception:
                metadata["namespace"] = default
    else:
        metadata["namespace"] = default

    return metadata


def fix_date(
    metadata: dict,
    date_type: str,
    default: datetime.datetime,
) -> dict:
    if date := metadata.get(date_type, None):
        try:
            if isinstance(date, datetime.datetime):
                return metadata
            elif isinstance(date, datetime.date):
                metadata[date_type] = datetime.datetime.combine(metadata[date_type], datetime.datetime.min.time())
            elif isinstance(date, str):
                metadata[date_type] = datetime.datetime.strptime(metadata[date_type], "%Y-%m-%dT%H:%M:%SZ")
            else:
                metadata[date_type] = default
        except Exception:
            metadata[date_type] = default
    else:
        metadata[date_type] = default

    return metadata


def fix_version(metadata: dict, default: str = "1.0.0") -> dict:
    if version := metadata.get("version", None):
        if not PATTERNS.version_compliance.match(version):
            metadata["version"] = default
    else:
        metadata["version"] = default

    return metadata


def fix_title(metadata: dict, default: str = "OWL Inferred Data Model") -> dict:
    if title := metadata.get("title", None):
        if not isinstance(title, str):
            metadata["title"] = default
        elif isinstance(title, str) and len(title) == 0:
            metadata["title"] = default
        elif isinstance(title, str) and len(title) > 255:
            metadata["title"] = metadata["title"][:255]
        else:
            pass
    else:
        metadata["title"] = default

    return metadata


def make_components_compliant(components: dict) -> dict:
    components = add_missing_classes(components)
    components = add_missing_value_types(components)
    components = add_default_property_to_dangling_classes(components)

    return components


def add_missing_classes(components: dict[str, list[dict]]) -> dict:
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


def add_missing_value_types(components: dict) -> dict:
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


def add_default_property_to_dangling_classes(components: dict[str, list[dict]]) -> dict:
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
