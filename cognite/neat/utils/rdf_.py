import re
from collections.abc import Iterable
from typing import Any, Literal, TypeAlias, overload

from cognite.client.utils.useful_types import SequenceNotStr
from pydantic import HttpUrl, TypeAdapter, ValidationError
from rdflib import Literal as RdfLiteral
from rdflib import Namespace, URIRef

Triple: TypeAlias = tuple[URIRef, URIRef, RdfLiteral | URIRef]


@overload
def remove_namespace_from_uri(
    URI: URIRef | str,
    *,
    special_separator: str = "#_",
    validation: Literal["full", "prefix"] = "prefix",
) -> str: ...


@overload
def remove_namespace_from_uri(
    URI: SequenceNotStr[URIRef | str],
    *,
    special_separator: str = "#_",
    validation: Literal["full", "prefix"] = "prefix",
) -> list[str]: ...


def remove_namespace_from_uri(
    URI: URIRef | str | SequenceNotStr[URIRef | str],
    *,
    special_separator: str = "#_",
    validation: Literal["full", "prefix"] = "prefix",
) -> str | list[str]:
    """Removes namespace from URI

    Args
        URI: URIRef | str
            URI of an entity
        special_separator : str
            Special separator to use instead of # or / if present in URI
            Set by default to "#_" which covers special client use case
        validation: str
            Validation type to use for URI. If set to "full", URI will be validated using pydantic
            If set to "prefix", only check if URI starts with http or https will be made

    Returns
        Entities id without namespace

    Examples:

        >>> remove_namespace_from_uri("http://www.example.org/index.html#section2")
        'section2'
        >>> remove_namespace_from_uri("http://www.example.org/index.html#section2", "http://www.example.org/index.html#section3")
        ('section2', 'section3')
    """
    is_single = False
    uris: Iterable[str | URIRef]
    if isinstance(URI, str | URIRef):
        uris = (URI,)
        is_single = True
    elif isinstance(URI, SequenceNotStr):
        # Assume that all elements in the tuple are of the same type following type hint
        uris = URI
    else:
        raise TypeError(f"URI must be of type URIRef or str, got {type(URI)}")

    output = []
    for u in uris:
        if validation == "full":
            try:
                _ = TypeAdapter(HttpUrl).validate_python(u)
                output.append(u.split(special_separator if special_separator in u else "#" if "#" in u else "/")[-1])
            except ValidationError:
                output.append(str(u))
        else:
            if u.lower().startswith("http"):
                output.append(u.split(special_separator if special_separator in u else "#" if "#" in u else "/")[-1])
            else:
                output.append(str(u))

    return output[0] if is_single else output


def get_namespace(URI: URIRef, special_separator: str = "#_") -> str:
    """Removes namespace from URI

    Parameters
    ----------
    URI : URIRef
        URI of an entity
    special_separator : str
        Special separator to use instead of # or / if present in URI
        Set by default to "#_" which covers special client use case

    Returns
    -------
    str
        Entity id without namespace
    """
    if special_separator in URI:
        return URI.split(special_separator)[0] + special_separator
    elif "#" in URI:
        return URI.split("#")[0] + "#"
    else:
        return "/".join(URI.split("/")[:-1]) + "/"


def as_neat_compliant_uri(uri: URIRef) -> URIRef:
    namespace = get_namespace(uri)
    id_ = remove_namespace_from_uri(uri)
    compliant_uri = re.sub(r"[^a-zA-Z0-9-_.]", "", id_)
    return URIRef(f"{namespace}{compliant_uri}")


def convert_rdflib_content(content: RdfLiteral | URIRef | dict | list) -> Any:
    if isinstance(content, RdfLiteral) or isinstance(content, URIRef):
        return content.toPython()
    elif isinstance(content, dict):
        return {key: convert_rdflib_content(value) for key, value in content.items()}
    elif isinstance(content, list):
        return [convert_rdflib_content(item) for item in content]
    else:
        return content


def uri_to_short_form(URI: URIRef, prefixes: dict[str, Namespace]) -> str | URIRef:
    """Returns the short form of a URI if its namespace is present in the prefixes dict,
    otherwise returns the URI itself

    Args:
        URI: URI to be converted to form prefix:entityName
        prefixes: dict of prefixes

    Returns:
        shortest form of the URI if its namespace is present in the prefixes dict,
        otherwise returns the URI itself
    """
    uris: set[str | URIRef] = {URI}
    for prefix, namespace in prefixes.items():
        if URI.startswith(namespace):
            uris.add(f"{prefix}:{URI.replace(namespace, '')}")
    return min(uris, key=len)


def _traverse(hierarchy: dict, graph: dict, names: list[str]) -> dict:
    """traverse the graph and return the hierarchy"""
    for name in names:
        hierarchy[name] = _traverse({}, graph, graph[name])
    return hierarchy


def get_inheritance_path(child: Any, child_parent: dict[Any, list[Any]]) -> list:
    """Returns the inheritance path for a given child

    Args:
        child: Child class
        child_parent: Dictionary of child to parent relationship

    Returns:
        Inheritance path for a given child

    !!! note "No Circular Inheritance"
        This method assumes that the child_parent dictionary is a tree and does not contain any cycles.
    """
    path = []
    if child in child_parent:
        path.extend(child_parent[child])
        for parent in child_parent[child]:
            path.extend(get_inheritance_path(parent, child_parent))
    return path
