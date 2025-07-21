from typing import cast
from urllib.parse import quote

from rdflib import BNode, Graph
from rdflib.plugins.sparql import prepareQuery
from rdflib.query import ResultRow

from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._issues.errors._general import NeatValueError
from cognite.neat.core._issues.warnings._resources import (
    ResourceRedefinedWarning,
    ResourceRetrievalWarning,
)
from cognite.neat.core._utils.rdf_ import convert_rdflib_content


def parse_concepts(
    graph: Graph, query: str, parameters: set, language: str, issue_list: IssueList
) -> tuple[dict, IssueList]:
    """Parse concepts from graph

    Args:
        graph: Graph containing concept definitions
        query: SPARQL query to use for parsing concepts
        parameters: Set of parameters to extract from the query results
        language: Language to use for parsing, by default "en"
        issue_list: List to collect issues during parsing

    Returns:
        Dataframe containing owl classes
    """

    concepts: dict[str, dict] = {}

    query = prepareQuery(query.format(language=language), initNs={k: v for k, v in graph.namespaces()})

    for raw in graph.query(query):
        res: dict = convert_rdflib_content(cast(ResultRow, raw).asdict(), True)
        res = {key: res.get(key, None) for key in parameters}

        # Quote the concept id to ensure it is web-safe
        res["concept"] = quote(res["concept"], safe="")

        concept_id = res["concept"]

        # Safeguarding against incomplete semantic definitions
        if res["implements"] and isinstance(res["implements"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    concept_id,
                    "implements",
                    error=("Unable to determine concept that is being implemented"),
                )
            )
            continue

        if concept_id not in concepts:
            concepts[concept_id] = res
        else:
            # Handling implements
            if concepts[concept_id]["implements"] and isinstance(concepts[concept_id]["implements"], list):
                if res["implements"] not in concepts[concept_id]["implements"]:
                    concepts[concept_id]["implements"].append(res["implements"])

            elif concepts[concept_id]["implements"] and isinstance(concepts[concept_id]["implements"], str):
                concepts[concept_id]["implements"] = [concepts[concept_id]["implements"]]

                if res["implements"] not in concepts[concept_id]["implements"]:
                    concepts[concept_id]["implements"].append(res["implements"])
            elif res["implements"]:
                concepts[concept_id]["implements"] = [res["implements"]]

            handle_meta("concept", concepts, concept_id, res, "name", issue_list)
            handle_meta("concept", concepts, concept_id, res, "description", issue_list)

    if not concepts:
        issue_list.append(NeatValueError("Unable to parse concepts"))

    return concepts, issue_list


def parse_properties(
    graph: Graph, query: str, parameters: set, language: str, issue_list: IssueList
) -> tuple[dict, IssueList]:
    """Parse properties from graph

    Args:
        graph: Graph containing property definitions
        query: SPARQL query to use for parsing properties
        parameters: Set of parameters to extract from the query results
        language: Language to use for parsing, by default "en"
        issue_list: List to collect issues during parsing

    Returns:
        Dataframe containing owl classes
    """

    properties: dict[str, dict] = {}

    query = prepareQuery(query.format(language=language), initNs={k: v for k, v in graph.namespaces()})

    for raw in graph.query(query):
        res: dict = convert_rdflib_content(cast(ResultRow, raw).asdict(), True)
        res = {key: res.get(key, None) for key in parameters}

        # Quote the concept id to ensure it is web-safe
        res["property_"] = quote(res["property_"], safe="")
        property_id = res["property_"]

        # Skip Bnode
        if isinstance(res["concept"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    property_id,
                    "property",
                    error="Cannot determine concept of property as it is a blank node",
                )
            )
            continue

        # Skip Bnode
        if isinstance(res["value_type"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    property_id,
                    "property",
                    error="Unable to determine value type of property as it is a blank node",
                )
            )
            continue

        # Quote the concept and value_type to ensure they are web-safe
        res["concept"] = quote(res["concept"], safe="") if res["concept"] else "#N/A"
        res["value_type"] = quote(res["value_type"], safe="") if res["value_type"] else "#N/A"

        id_ = f"{res['concept']}.{res['property_']}"

        if id_ not in properties:
            properties[id_] = res
            properties[id_]["value_type"] = [properties[id_]["value_type"]]
        else:
            handle_meta("property", properties, id_, res, "name", issue_list)
            handle_meta(
                "property",
                properties,
                id_,
                res,
                "description",
                issue_list,
            )

            # Handling multi-value types
            if res["value_type"] not in properties[id_]["value_type"]:
                properties[id_]["value_type"].append(res["value_type"])

    for prop in properties.values():
        prop["value_type"] = ", ".join(prop["value_type"])

    if not properties:
        issue_list.append(NeatValueError("Unable to parse properties"))

    return properties, issue_list


def handle_meta(
    resource_type: str,
    resources: dict[str, dict],
    resource_id: str,
    res: dict,
    feature: str,
    issue_list: IssueList,
) -> None:
    if not resources[resource_id][feature] and res[feature]:
        resources[resource_id][feature] = res[feature]

    # RAISE warning only if the feature is being redefined
    elif resources[resource_id][feature] and res[feature]:
        issue_list.append(
            ResourceRedefinedWarning(
                identifier=resource_id,
                resource_type=resource_type,
                feature=feature,
                current_value=resources[resource_id][feature],
                new_value=res[feature],
            )
        )
