from typing import Any, cast

from rdflib.query import Result
from rdflib.term import Node


def rdf_result_to_api_response(result: Result) -> dict[str, Any]:
    response: dict[str, Any] = {"fields": [], "rows": []}
    if result.vars is None:
        result.vars = ["s", "p", "o"]  # type: ignore[list-item]

    for field in result.vars:
        response["fields"].append(field)
    for row in result:
        rrow = {field: cast(tuple[Node, Node, Node], row)[i] for i, field in enumerate(result.vars)}
        response["rows"].append(rrow)
    return response
