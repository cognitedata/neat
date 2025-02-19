from typing import cast

from rdflib import BNode, Graph
from rdflib.plugins.sparql import prepareQuery
from rdflib.query import ResultRow

from cognite.neat._issues._base import IssueList
from cognite.neat._issues.errors._general import NeatValueError
from cognite.neat._issues.warnings._resources import (
    ResourceRedefinedWarning,
    ResourceRetrievalWarning,
)
from cognite.neat._utils.rdf_ import convert_rdflib_content


def parse_classes(graph: Graph, query: str, language: str, issue_list: IssueList) -> tuple[dict, IssueList]:
    """Parse classes from graph

    Args:
        graph: Graph containing classes definitions
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing owl classes
    """

    classes: dict[str, dict] = {}

    query = prepareQuery(query.format(language=language), initNs={k: v for k, v in graph.namespaces()})
    expected_keys = [str(v) for v in query.algebra._vars]

    for raw in graph.query(query):
        res: dict = convert_rdflib_content(cast(ResultRow, raw).asdict(), True)
        res = {key: res.get(key, None) for key in expected_keys}

        class_id = res["class_"]

        # Safeguarding against incomplete semantic definitions
        if res["implements"] and isinstance(res["implements"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    class_id,
                    "implements",
                    error=("Unable to determine class that is being implemented"),
                )
            )
            continue

        if class_id not in classes:
            classes[class_id] = res
        else:
            # Handling implements
            if classes[class_id]["implements"] and isinstance(classes[class_id]["implements"], list):
                if res["implements"] not in classes[class_id]["implements"]:
                    classes[class_id]["implements"].append(res["implements"])

            elif classes[class_id]["implements"] and isinstance(classes[class_id]["implements"], str):
                classes[class_id]["implements"] = [classes[class_id]["implements"]]

                if res["implements"] not in classes[class_id]["implements"]:
                    classes[class_id]["implements"].append(res["implements"])
            elif res["implements"]:
                classes[class_id]["implements"] = [res["implements"]]

            handle_meta("class_", classes, class_id, res, "name", issue_list)
            handle_meta("class_", classes, class_id, res, "description", issue_list)

    if not classes:
        issue_list.append(NeatValueError("Unable to parse classes"))

    return classes, issue_list


def parse_properties(graph: Graph, query: str, language: str, issue_list: IssueList) -> tuple[dict, IssueList]:
    """Parse properties from graph

    Args:
        graph: Graph containing owl classes
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing owl classes
    """

    properties: dict[str, dict] = {}

    query = prepareQuery(query.format(language=language), initNs={k: v for k, v in graph.namespaces()})
    expected_keys = [str(v) for v in query.algebra._vars]

    for raw in graph.query(query):
        res: dict = convert_rdflib_content(cast(ResultRow, raw).asdict(), True)
        res = {key: res.get(key, None) for key in expected_keys}

        property_id = res["property_"]

        # Safeguarding against incomplete semantic definitions
        if not res["class_"] or isinstance(res["class_"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    property_id,
                    "property",
                    error=("Unable to determine to what class property is being defined"),
                )
            )
            continue

        # Safeguarding against incomplete semantic definitions
        if not res["value_type"] or isinstance(res["value_type"], BNode):
            issue_list.append(
                ResourceRetrievalWarning(
                    property_id,
                    "property",
                    error=("Unable to determine value type of property"),
                )
            )
            continue

        id_ = f"{res['class_']}.{res['property_']}"

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
):
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
