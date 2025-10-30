from typing import Any, Literal, cast
from urllib.parse import quote

from rdflib import BNode, Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral
from rdflib.plugins.sparql import prepareQuery
from rdflib.query import ResultRow

from cognite.neat.v0.core._constants import cognite_prefixes
from cognite.neat.v0.core._data_model.models.entities._constants import Unknown
from cognite.neat.v0.core._data_model.models.entities._single_value import ConceptEntity
from cognite.neat.v0.core._issues._base import IssueList
from cognite.neat.v0.core._issues.errors._general import NeatValueError
from cognite.neat.v0.core._issues.warnings._resources import (
    ResourceRedefinedWarning,
    ResourceRetrievalWarning,
)
from cognite.neat.v0.core._utils.rdf_ import remove_namespace_from_uri, uri_to_entity_components


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
    prefixes = cognite_prefixes()

    for raw in graph.query(query):
        res: dict = convert_rdflib_content(
            cast(ResultRow, raw).asdict(), uri_handling="as-concept-entity", prefixes=prefixes
        )
        res = {key: res.get(key, None) for key in parameters}

        # Safeguarding against incomplete semantic definitions
        if res["implements"] and isinstance(res["implements"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    res["concept"],
                    "implements",
                    error=("Unable to determine concept that is being implemented"),
                )
            )
            continue

        # sanitize the concept and implements
        res["concept"] = sanitize_entity(res["concept"])
        res["implements"] = sanitize_entity(res["implements"]) if res["implements"] else None

        concept_id = res["concept"]

        if concept_id not in concepts:
            concepts[concept_id] = res
        else:
            # Handling implements
            if concepts[concept_id]["implements"] and isinstance(concepts[concept_id]["implements"], list):
                if res["implements"] and res["implements"] not in concepts[concept_id]["implements"]:
                    concepts[concept_id]["implements"].append(res["implements"])

            elif concepts[concept_id]["implements"] and isinstance(concepts[concept_id]["implements"], str):
                concepts[concept_id]["implements"] = [concepts[concept_id]["implements"]]

                if res["implements"] and res["implements"] not in concepts[concept_id]["implements"]:
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
    prefixes = cognite_prefixes()

    for raw in graph.query(query):
        res: dict = convert_rdflib_content(
            cast(ResultRow, raw).asdict(), uri_handling="as-concept-entity", prefixes=prefixes
        )
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

        # Quote the concept and value_type if they exist if not signal neat that they are not available
        res["concept"] = sanitize_entity(res["concept"]) if res["concept"] else str(Unknown)
        res["value_type"] = sanitize_entity(res["value_type"]) if res["value_type"] else str(Unknown)

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

    current_value = resources[resource_id][feature]
    new_value = res[feature]

    if not current_value and new_value:
        resources[resource_id][feature] = new_value
    elif current_value and new_value and current_value != new_value:
        issue_list.append(
            ResourceRedefinedWarning(
                identifier=resource_id,
                resource_type=resource_type,
                feature=feature,
                current_value=current_value,
                new_value=new_value,
            )
        )


def convert_rdflib_content(
    content: RdfLiteral | URIRef | dict | list,
    uri_handling: Literal["skip", "remove-namespace", "as-concept-entity"] = "skip",
    prefixes: dict[str, Namespace] | None = None,
) -> Any:
    """Converts rdflib content to a more Python-friendly format.

    Args:
        content: The content to convert, can be a RdfLiteral, URIRef, dict, or list.
        uri_handling: How to handle URIs. Options are:
            - "skip": Leave URIs as is.
            - "remove-namespace": Remove the namespace from URIs.
            - "short-form": Convert URIs to a short form using prefixes.

    """
    if isinstance(content, RdfLiteral):
        return content.toPython()
    elif isinstance(content, URIRef):
        if uri_handling == "remove-namespace":
            return remove_namespace_from_uri(content)
        elif uri_handling == "as-concept-entity":
            if components := uri_to_entity_components(content, prefixes or {}):
                return ConceptEntity(prefix=components[0], suffix=components[3], version=components[2])
            # fallback to "remove-namespace"
            else:
                return convert_rdflib_content(content, uri_handling="remove-namespace", prefixes=prefixes)
        else:
            return content.toPython()
    elif isinstance(content, dict):
        return {key: convert_rdflib_content(value, uri_handling, prefixes) for key, value in content.items()}
    elif isinstance(content, list):
        return [convert_rdflib_content(item, uri_handling, prefixes) for item in content]
    else:
        return content


def sanitize_entity(entity: str | ConceptEntity, safe: str = "") -> str:
    """Sanitize an entity to ensure it yields entity form that will pass downstream validation.

    Args:
        entity: The entity to sanitize. Can be a string or a ConceptEntity.
        safe: Characters that should not be quoted during sanitization.

    Returns:
        A web-safe string representation of the entity
    """
    if isinstance(entity, str):
        return quote(entity, safe=safe)
    # if it already we dont need to quote it so we return its string representation
    elif isinstance(entity, ConceptEntity):
        return str(entity)
    else:
        raise ValueError(f"Invalid entity type: {type(entity)}. Expected str, ConceptEntity.")
