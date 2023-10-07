"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

# TODO: if this module grows too big, split it into several files and place under ./converter directory

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from rdflib import DC, DCTERMS, OWL, RDF, RDFS, Graph

from cognite.neat.rules import exceptions
from cognite.neat.rules.parser import parse_rules_from_excel_file
from cognite.neat.utils.utils import generate_exception_report, get_namespace, remove_namespace


def _create_default_metadata_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Metadata pydantic model
    return {
        "header": (
            "namespace",
            "prefix",
            "dataModelName",
            "cdfSpaceName",
            "version",
            "isCurrentVersion",
            "created",
            "updated",
            "title",
            "description",
            "creator",
            "contributor",
            "rights",
            "license",
        )
    }


def _create_default_classes_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Class pydantic model
    return {
        "helper_row": ("Data Model Definition", "", "", "", "State", "", "", "Knowledge acquisition log", "", "", ""),
        "header": (
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
        ),
    }


def _create_default_properties_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Property pydantic model
    return {
        "helper_row": (
            "Data Model Definition",
            "",
            "",
            "",
            "",
            "",
            "",
            "State",
            "",
            "",
            "Knowledge acquisition log",
            "",
            "",
            "",
        ),
        "header": (
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
            "Match",
            "Comment",
        ),
    }


def owl2excel(owl_filepath: Path, excel_filepath: Path | None = None, validate_results: bool = True):
    """Convert owl ontology to transformation rules and then stored them as an Excel file.

    Args:
        owl_filepath: Path to OWL ontology
        excel_filepath: Path to save transformation rules. If None is passed, the
                        file will be "owl_filepath.parent / transformation_rules.xlsx".
        validate_results: Whether to validate generated Excel file and create validation report, by default True

    """

    owl_filepath = Path(owl_filepath)
    if excel_filepath:
        excel_filepath = Path(excel_filepath)
    else:
        excel_filepath = owl_filepath.parent / "transformation_rules.xlsx"

    graph = Graph()
    try:
        graph.parse(owl_filepath)
    except Exception as e:
        raise Exception(f"Could not parse owl file: {e}") from e

    # bind key namespaces
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("dcterms", DCTERMS)
    graph.bind("dc", DC)

    with pd.ExcelWriter(excel_filepath) as writer:
        _parse_owl_metadata_df(graph).to_excel(writer, sheet_name="Metadata", header=False)
        _parse_owl_classes_df(graph).to_excel(writer, sheet_name="Classes", index=False, header=False)
        _parse_owl_properties_df(graph).to_excel(writer, sheet_name="Properties", index=False, header=False)

    if validate_results:
        _validate_excel_file(excel_filepath)


def _parse_owl_metadata_df(graph: Graph, parsing_config: dict | None = None) -> pd.DataFrame:
    """Parse owl metadata from graph to pandas dataframe.

    Args:
        graph: Graph containing owl metadata
        parsing_config: Configuration for parsing. Defaults to None.

    Returns:
        Dataframe containing owl metadata
    """
    if parsing_config is None:
        parsing_config = _create_default_metadata_parsing_config()

    query = """
    SELECT ?namespace ?prefix ?dataModelName ?cdfSpaceName ?version ?isCurrentVersion
           ?created ?updated ?title ?description ?creator ?contributor ?rights ?license
    WHERE {
        ?namespace a owl:Ontology .
        OPTIONAL {?namespace owl:versionInfo ?version }.
        OPTIONAL {?namespace dcterms:creator ?creator }.
        OPTIONAL {?namespace dcterms:title ?title }.
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

    raw_df = pd.DataFrame(list(graph.query(query)), columns=parsing_config["header"])
    if raw_df.empty:
        return raw_df
    raw_df.replace(np.nan, "", regex=True, inplace=True)

    clean_list = [
        [
            raw_df.namespace.unique()[0],
            raw_df.prefix.unique()[0],
            raw_df.dataModelName.unique()[0],
            raw_df.cdfSpaceName.unique()[0],
            raw_df.version.unique()[0],
            True,
            raw_df.created.unique()[0],
            raw_df.updated.unique()[0],
            raw_df.title.unique()[0],
            raw_df.description.unique()[0],
            ", ".join(list(raw_df.creator.unique())),
            ", ".join(list(raw_df.contributor.unique())),
            raw_df.rights.unique()[0],
            raw_df.license.unique()[0],
        ]
    ]

    return pd.DataFrame(clean_list, columns=parsing_config["header"]).T


def _parse_owl_classes_df(graph: Graph, parsing_config: dict | None = None) -> pd.DataFrame:
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
    if parsing_config is None:
        parsing_config = _create_default_classes_parsing_config()

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

    raw_df = pd.DataFrame(list(graph.query(query)), columns=parsing_config["header"])
    if raw_df.empty:
        raw_df = pd.concat([raw_df, pd.DataFrame([len(raw_df) * [""]])], ignore_index=True)
        return raw_df
    raw_df.replace(np.nan, "", regex=True, inplace=True)

    raw_df.Source = raw_df.Class.apply(lambda x: get_namespace(x))
    raw_df.Class = raw_df.Class.apply(lambda x: remove_namespace(x))
    raw_df["Source Entity Name"] = raw_df.Class
    raw_df["Match"] = len(raw_df) * ["exact"]
    raw_df["Parent Class"] = raw_df["Parent Class"].apply(lambda x: remove_namespace(x))

    grouped_df = raw_df.groupby("Class")

    clean_list = [
        [
            class_,
            group_df["Name"].unique()[0],
            "\n".join(list(group_df.Description.unique())),
            ", ".join(list(group_df["Parent Class"].unique())),
            group_df.Deprecated.unique()[0],
            group_df["Deprecation Date"].unique()[0],
            group_df["Replaced By"].unique()[0],
            group_df["Source"].unique()[0],
            group_df["Source Entity Name"].unique()[0],
            group_df["Match"].unique()[0],
            group_df["Comment"].unique()[0],
        ]
        for class_, group_df in grouped_df
    ]
    return pd.DataFrame([parsing_config["helper_row"], parsing_config["header"], *clean_list])


def _parse_owl_properties_df(graph: Graph, parsing_config: dict | None = None) -> pd.DataFrame:
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
    if parsing_config is None:
        parsing_config = _create_default_properties_parsing_config()

    query = """
    SELECT ?class ?property ?name ?description ?type ?minCount ?maxCount
    ?deprecated ?deprecationDate ?replacedBy ?source ?sourceEntity ?match ?comment
    WHERE {
        ?property a ?propertyType.
        FILTER (?propertyType IN (owl:ObjectProperty, owl:DatatypeProperty ) )
        OPTIONAL {?property rdfs:domain ?class }.
        OPTIONAL {?property rdfs:range ?type }.
        OPTIONAL {?property rdfs:label ?name }.
        OPTIONAL {?property rdfs:comment ?description} .
        FILTER (!isBlank(?property))
        FILTER (!bound(?class) || !isBlank(?class))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        OPTIONAL {?property owl:deprecated ?deprecated} .
    }
    """

    raw_df = pd.DataFrame(list(graph.query(query)), columns=parsing_config["header"])
    if raw_df.empty:
        return raw_df
    raw_df.replace(np.nan, "", regex=True, inplace=True)

    raw_df.Source = raw_df.Property.apply(lambda x: get_namespace(x))
    raw_df.Class = raw_df.Class.apply(lambda x: remove_namespace(x))
    raw_df.Property = raw_df.Property.apply(lambda x: remove_namespace(x))
    raw_df.Type = raw_df.Type.apply(lambda x: remove_namespace(x))
    raw_df["Source Entity Name"] = raw_df.Property
    raw_df["Match"] = len(raw_df) * ["exact"]

    class_grouped_dfs = raw_df.groupby("Class")

    clean_list = []

    for class_, class_grouped_df in class_grouped_dfs:
        property_grouped_dfs = class_grouped_df.groupby("Property")
        for property_, property_grouped_df in property_grouped_dfs:
            clean_list += [
                [
                    class_,
                    property_,
                    property_grouped_df["Name"].unique()[0],
                    "\n".join(list(property_grouped_df.Description.unique())),
                    property_grouped_df.Type.unique()[0],
                    property_grouped_df["Min Count"].unique()[0],
                    property_grouped_df["Max Count"].unique()[0],
                    property_grouped_df.Deprecated.unique()[0],
                    property_grouped_df["Deprecation Date"].unique()[0],
                    property_grouped_df["Replaced By"].unique()[0],
                    property_grouped_df["Source"].unique()[0],
                    property_grouped_df["Source Entity Name"].unique()[0],
                    property_grouped_df["Match"].unique()[0],
                    property_grouped_df["Comment"].unique()[0],
                ]
            ]

    return pd.DataFrame([parsing_config["helper_row"], parsing_config["header"], *clean_list])


def _validate_excel_file(excel_filepath: Path):
    _, validation_errors, validation_warnings = parse_rules_from_excel_file(excel_filepath, return_report=True)

    report = ""
    if validation_errors:
        warnings.warn(
            exceptions.OWLGeneratedTransformationRulesHasErrors().message,
            category=exceptions.OWLGeneratedTransformationRulesHasErrors,
            stacklevel=2,
        )
        report = generate_exception_report(validation_errors, "Errors")

    if validation_warnings:
        warnings.warn(
            exceptions.OWLGeneratedTransformationRulesHasWarnings().message,
            category=exceptions.OWLGeneratedTransformationRulesHasWarnings,
            stacklevel=2,
        )
        report += generate_exception_report(validation_warnings, "Warnings")

    if report:
        with (excel_filepath.parent / "report.txt").open("w") as f:
            f.write(report)
