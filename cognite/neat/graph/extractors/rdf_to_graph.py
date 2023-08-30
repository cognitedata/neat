from pathlib import Path

from rdflib import Graph, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE, DEFAULT_URI, PREFIXES

__all__ = ["rdf_file_to_graph"]


def rdf_file_to_graph(
    filepath: Path,
    base_prefix: str = DEFAULT_URI,
    base_namespace: Namespace = DEFAULT_NAMESPACE,
    prefixes: dict[str, Namespace] = PREFIXES,
) -> Graph:
    """Created rdflib Graph instance loaded with RDF triples from file

    Args:
        filepath: Path to the RDF file
        base_prefix: base prefix for URIs. Defaults to DEFAULT_URI.
        base_namespace: base namespace for URIs . Defaults to DEFAULT_NAMESPACE.
        prefixes: Dictionary of prefixes to bind to graph. Defaults to PREFIXES.

    Returns:
        Graph instance loaded with RDF triples from file
    """
    graph = Graph()
    if filepath.is_file():
        graph.parse(filepath, publicID=base_namespace)
    else:
        for filename in filepath.iterdir():
            if filename.is_file():
                graph.parse(filename, publicID=base_namespace)

    graph.bind(base_prefix, base_namespace)
    if prefixes:
        for prefix, namespace in prefixes.items():
            graph.bind(prefix, namespace)

    return graph
