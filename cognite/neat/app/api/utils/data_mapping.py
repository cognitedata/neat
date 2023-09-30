from typing import Any

from rdflib.query import Result


def rdf_result_to_api_response(result: Result) -> dict[str, Any]:
    response = {"fields": [], "rows": []}
    if result.vars is None:
        result.vars = ["s", "p", "o"]
    for field in result.vars:
        response["fields"].append(field)
    for row in result:
        rrow = {field: row[i] for i, field in enumerate(result.vars)}
        response["rows"].append(rrow)
    return response
