import re
from collections.abc import Iterable
from typing import Any, Literal, TypeAlias, overload

from cognite.client.utils.useful_types import SequenceNotStr
from pydantic import HttpUrl, TypeAdapter, ValidationError
from rdflib import Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral

from cognite.neat._constants import SPACE_URI_PATTERN

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
    return split_uri(URI, special_separator)[0]


def namespace_as_space(namespace: str) -> str | None:
    if match := SPACE_URI_PATTERN.match(namespace):
        return match.group("space")
    return None


def split_uri(URI: URIRef, special_separator: str = "#_") -> tuple[str, str]:
    """Splits URI into namespace and entity name

    Parameters
    ----------
    URI : URIRef
        URI of an entity
    special_separator : str
        Special separator to use instead of # or / if present in URI
        Set by default to "#_" which covers special client use case

    Returns
    -------
    tuple[str, str]
        Tuple of namespace and entity name
    """
    if special_separator in URI:
        namespace, rest = URI.split(special_separator, maxsplit=1)
        namespace += special_separator
    elif "#" in URI:
        namespace, rest = URI.split("#", maxsplit=1)
        namespace += "#"
    else:
        namespace, rest = URI.rsplit("/", maxsplit=1)
        namespace += "/"
    return namespace, rest


def as_neat_compliant_uri(uri: URIRef) -> URIRef:
    namespace = get_namespace(uri)
    id_ = remove_namespace_from_uri(uri)
    compliant_uri = re.sub(r"[^a-zA-Z0-9-_.]", "", id_)
    return URIRef(f"{namespace}{compliant_uri}")


def convert_rdflib_content(content: RdfLiteral | URIRef | dict | list, remove_namespace: bool = False) -> Any:
    if isinstance(content, RdfLiteral):
        return content.toPython()
    elif isinstance(content, URIRef):
        return remove_namespace_from_uri(content) if remove_namespace else content.toPython()
    elif isinstance(content, dict):
        return {key: convert_rdflib_content(value, remove_namespace) for key, value in content.items()}
    elif isinstance(content, list):
        return [convert_rdflib_content(item, remove_namespace) for item in content]
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


def get_inheritance_path(child: Any, child_parent: dict[Any, set[Any]]) -> list[Any]:
    """Returns the inheritance path for a given child

    Args:
        child: Child class
        child_parent: Dictionary of child to parent relationship

    Returns:
        Inheritance path for a given child

    !!! note "No Circular Inheritance"
        This method assumes that the child_parent dictionary is a tree and does not contain any cycles.
    """
    path: list[Any] = []
    if child in child_parent:
        path.extend(child_parent[child])
        for parent in child_parent[child]:
            path.extend(get_inheritance_path(parent, child_parent))
    return path


def add_triples_in_batch(graph: Graph, triples: Iterable[Triple], batch_size: int = 10_000) -> None:
    """Adds triples to the graph store in batches.

    Args:
        triples: list of triples to be added to the graph store
        batch_size: Batch size of triples per commit, by default 10_000
        verbose: Verbose mode, by default False
    """

    commit_counter = 0
    number_of_written_triples = 0

    def check_commit(force_commit: bool = False):
        """Commit nodes to the graph if batch counter is reached or if force_commit is True"""
        nonlocal commit_counter
        nonlocal number_of_written_triples
        if force_commit:
            number_of_written_triples += commit_counter
            graph.commit()
            return
        commit_counter += 1
        if commit_counter >= batch_size:
            number_of_written_triples += commit_counter
            graph.commit()
            commit_counter = 0

    for triple in triples:
        graph.add(triple)
        check_commit()

    check_commit(force_commit=True)


def remove_triples_in_batch(graph: Graph, triples: Iterable[Triple], batch_size: int = 10_000) -> None:
    """Removes triples from the graph store in batches.

    Args:
        triples: list of triples to be removed from the graph store
        batch_size: Batch size of triples per commit, by default 10_000
    """
    batch_count = 0

    def check_commit(force_commit: bool = False):
        """Commit nodes to the graph if batch counter is reached or if force_commit is True"""
        nonlocal batch_count
        batch_count += 1
        if force_commit or batch_count >= batch_size:
            graph.commit()
            batch_count = 0
            return

    for triple in triples:
        graph.remove(triple)
        check_commit()
    check_commit(force_commit=True)


def remove_instance_ids_in_batch(graph: Graph, instance_ids: Iterable[URIRef], batch_size: int = 1_000) -> None:
    """Removes all triples related to the given instances in the graph store in batches.

    Args:
        graph: The graph store to remove triples from
        instance_ids:  list of instances to remove triples from
        batch_size:  Batch size of triples per commit, by default 10_000

    """
    batch_count = 0

    def check_commit(force_commit: bool = False):
        """Commit nodes to the graph if batch counter is reached or if force_commit is True"""
        nonlocal batch_count
        batch_count += 1
        if force_commit or batch_count >= batch_size:
            graph.commit()
            batch_count = 0
            return

    for instance_id in instance_ids:
        graph.remove((instance_id, None, None))
        check_commit()

    check_commit(force_commit=True)


def uri_display_name(thing: URIRef) -> str:
    if "https://cognitedata.com/dms/data-model/" in thing:
        return "DMS(" + ",".join(thing.replace("https://cognitedata.com/dms/data-model/", "").split("/")) + ")"
    elif "http://purl.org/cognite/neat/data-model/" in thing:
        return "NEAT(" + ",".join(thing.replace("http://purl.org/cognite/neat/data-model/", "").split("/")) + ")"
    return remove_namespace_from_uri(thing)
