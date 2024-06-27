"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

import warnings
from datetime import datetime
from typing import cast

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.legacy.rules import exceptions
from cognite.neat.legacy.rules.exporters._rules2rules import to_dms_name
from cognite.neat.legacy.rules.models.tables import Tables
from cognite.neat.utils.utils import get_namespace, remove_namespace, uri_to_short_form

from ._base import BaseImporter


class GraphImporter(BaseImporter):
    """
    Convert RDF graph, containing nodes and edges, to tables/ transformation rules / Excel file.

    Args:
        graph: RDF graph to be imported
        max_number_of_instance: Max number of instances to be analyzed for each class in RDF graph


    !!! Note
        Due to high degree of flexibility of RDF graphs, the RDF graph is not guaranteed to be
        converted to a complete and/or valid `Rules` object. Therefore, it is recommended to
        call method `to_raw_rules` to get the raw rules which one should export to Excel file
        using `exporter.ExcelExporter` and then manually edit the Excel file by checking
        validation report file produced by the exporter.

    """

    def __init__(self, graph: Graph, max_number_of_instance: int = -1):
        self.graph = graph
        self.max_number_of_instance = max_number_of_instance

    def to_tables(self) -> dict[str, pd.DataFrame]:
        data_model, prefixes = _graph_to_data_model_dict(self.graph, self.max_number_of_instance)

        return {
            Tables.metadata: _parse_metadata_df(),
            Tables.classes: _parse_classes_df(data_model, prefixes),
            Tables.properties: _parse_properties_df(data_model, prefixes),
            Tables.prefixes: _parse_prefixes_df(prefixes),
        }


def _create_default_properties_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Property pydantic model
    return {
        "header": (
            "Class",
            "Property",
            "Description",
            "Type",
            "Min Count",
            "Max Count",
            "Rule Type",
            "Rule",
            "Source",
            "Source Entity Name",
            "Match Type",
            "Comment",
        )
    }


def _create_default_classes_parsing_config() -> dict[str, tuple[str, ...]]:
    # TODO: these are to be read from Class pydantic model
    return {"header": ("Class", "Description", "Parent Class", "Source", "Source Entity Name", "Match Type", "Comment")}


def _parse_prefixes_df(prefixes: dict[str, Namespace]) -> pd.DataFrame:
    return pd.DataFrame.from_dict({"Prefix": list(prefixes.keys()), "URI": [str(uri) for uri in prefixes.values()]})


def _parse_metadata_df() -> pd.DataFrame:
    clean_list = {
        "namespace": "http://purl.org/cognite/neat/",
        "prefix": "playground",
        "external_id": "neat",
        "version": "1.0.0",
        "isCurrentVersion": True,
        "created": datetime.utcnow(),
        "updated": datetime.utcnow(),
        "title": "RDF Graph Inferred Data Model",
        "description": "This data model has been inferred with NEAT",
        "creator": "NEAT",
        "contributor": "NEAT",
        "rights": "Unknown rights of usage",
        "license": "Unknown license",
    }
    return pd.DataFrame(list(clean_list.items()), columns=["Key", "Value"])


def _parse_classes_df(data_model: dict, prefixes: dict, parsing_config: dict | None = None) -> pd.DataFrame:
    if parsing_config is None:
        parsing_config = _create_default_classes_parsing_config()

    class_rows = []

    for class_ in data_model:
        sanitized_class = to_dms_name(class_, "class")
        class_rows.append(
            [
                sanitized_class,
                None,
                None,
                str(prefixes[data_model[class_]["uri"].split(":")[0]]) + class_,
                class_,
                "exact",
                "Parsed from RDF graph",
            ]
        )

    return pd.DataFrame(class_rows, columns=parsing_config["header"])


def _parse_properties_df(data_model: dict, prefixes: dict, parsing_config: dict | None = None) -> pd.DataFrame:
    if parsing_config is None:
        parsing_config = _create_default_properties_parsing_config()

    property_rows = []

    for class_ in data_model:
        sanitized_class = to_dms_name(class_, "class")
        for property_ in data_model[class_]["properties"]:
            for type_ in data_model[class_]["properties"][property_]["value_type"]:
                sanitized_property = to_dms_name(property_, "property")

                max_count = max(data_model[class_]["properties"][property_]["occurrence"])

                property_rows.append(
                    [
                        sanitized_class,
                        sanitized_property,
                        None,
                        to_dms_name(type_, "value-type"),
                        0,  # setting min count to 0 to be more flexible (all properties are optional)
                        None if max_count > 1 else 1,
                        "rdfpath",
                        f'{data_model[class_]["uri"]}({data_model[class_]["properties"][property_]["uri"]})',
                        str(prefixes[data_model[class_]["properties"][property_]["uri"].split(":")[0]]) + property_,
                        property_,
                        "exact",
                        "Parsed from RDF graph",
                    ]
                )

    return pd.DataFrame(property_rows, columns=parsing_config["header"])


def _graph_to_data_model_dict(graph: Graph, max_number_of_instance: int = -1) -> tuple[dict, dict]:
    """Convert RDF graph to dictionary defining data model and prefixes of the graph

    Args:
        graph: RDF graph to be converted to TransformationRules object
        max_number_of_instance: Max number of instances to be considered for each class

    Returns:
        Tuple of data model and prefixes of the graph
    """
    data_model: dict[str, dict] = {}

    prefixes: dict[str, Namespace] = PREFIXES

    for class_ in _get_class_ids(graph):
        _add_uri_namespace_to_prefixes(class_, prefixes)
        class_name = remove_namespace(class_)

        if class_name in data_model:
            warnings.warn(
                exceptions.GraphClassNameCollision(class_name=class_name).message,
                category=exceptions.GraphClassNameCollision,
                stacklevel=2,
            )
            class_name = f"{class_name}_{len(data_model)+1}"

        data_model[class_name] = {"properties": {}, "uri": uri_to_short_form(class_, prefixes)}

        for instance in _get_class_instance_ids(graph, class_, max_number_of_instance):
            for property_, occurrence, data_type, object_type in _define_instance_properties(graph, instance):
                property_name = remove_namespace(property_)
                _add_uri_namespace_to_prefixes(property_, prefixes)

                type_ = data_type if data_type else object_type

                # this is to skip rdf:type property
                if not type_:
                    continue

                type_name = remove_namespace(type_)
                _add_uri_namespace_to_prefixes(type_, prefixes)

                if property_name not in data_model[class_name]["properties"]:
                    data_model[class_name]["properties"][property_name] = {
                        "occurrence": {occurrence.value},
                        "value_type": {type_name: {"uri": uri_to_short_form(type_, prefixes)}},
                        "uri": uri_to_short_form(property_, prefixes),
                    }

                elif type_name not in data_model[class_name]["properties"][property_name]["value_type"]:
                    data_model[class_name]["properties"][property_name]["value_type"][type_name] = {
                        "uri": uri_to_short_form(type_, prefixes)
                    }
                    warnings.warn(
                        exceptions.GraphClassPropertyMultiValueTypes(
                            class_name=class_name,
                            property_name=property_name,
                            types=list(data_model[class_name]["properties"][property_name]["value_type"].keys()),
                        ).message,
                        category=exceptions.GraphClassPropertyMultiValueTypes,
                        stacklevel=3,
                    )

                elif occurrence.value not in data_model[class_name]["properties"][property_name]["occurrence"]:
                    data_model[class_name]["properties"][property_name]["occurrence"].add(occurrence.value)

                    warnings.warn(
                        exceptions.GraphClassPropertyMultiOccurrence(
                            class_name=class_name, property_name=property_name
                        ).message,
                        category=exceptions.GraphClassPropertyMultiOccurrence,
                        stacklevel=3,
                    )
                else:
                    continue

    return data_model, prefixes


def _add_uri_namespace_to_prefixes(URI: URIRef, prefixes: dict[str, Namespace]):
    """Add URI to prefixes dict if not already present

    Args:
        URI: URI from which namespace is being extracted
        prefixes: Dict of prefixes and namespaces
    """
    if Namespace(get_namespace(URI)) not in prefixes.values():
        prefixes[f"prefix-{len(prefixes)+1}"] = Namespace(get_namespace(URI))


def _get_class_ids(graph: Graph) -> list[URIRef]:
    """Get instances ids for a given class

    Args:
        graph: Graph containing class instances
        class_: Class for which instances are to be found
        namespace: Namespace of given class (to avoid writing long URIs)
        limit: Max number of instances to return, by default -1 meaning all instances

    Returns:
        List of class instance URIs
    """

    query_statement = """SELECT ?class (count(?s) as ?instances )
                                WHERE { ?s a ?class . }
                                group by ?class order by DESC(?instances)"""

    return [cast(tuple[URIRef, int], res)[0] for res in list(graph.query(query_statement))]


def _get_class_instance_ids(graph: Graph, class_id: URIRef, max_number_of_instance: int = -1) -> list[URIRef]:
    """Get instances ids for a given class

    Args:
        graph: Graph containing class instances
        class_id: Class id for which instances are to be found

    Returns:
        List of class instance URIs
    """

    query_statement = "SELECT DISTINCT ?subject WHERE { ?subject a <class> .}".replace("class", class_id)
    if max_number_of_instance > 0:
        query_statement += f" LIMIT {max_number_of_instance}"
    return [cast(tuple[URIRef], res)[0] for res in list(graph.query(query_statement))]


def _define_instance_properties(
    graph: Graph, instance_id: URIRef
) -> list[tuple[URIRef, Literal, URIRef | None, None | URIRef]]:
    """Get properties of a given instance

    Args:
        graph: Graph containing class instances
        instance_id: Instance id for which properties are to be found and defined

    Returns:
        List of properties of a given instance
    """
    query_statement = """SELECT ?property (count(?property) as ?occurrence) ?dataType ?objectType
                         WHERE {<instance_id> ?property ?value .
                                BIND(datatype(?value) AS ?dataType)
                                OPTIONAL {?value rdf:type ?objectType .}
                                }
                         GROUP BY ?property ?dataType ?objectType"""

    results = graph.query(query_statement.replace("instance_id", instance_id))

    return [cast(tuple[URIRef, Literal, URIRef | None, None | URIRef], res) for res in list(results)]
