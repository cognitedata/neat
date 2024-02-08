from pathlib import Path

from rdflib import Graph, Namespace

from cognite.neat.constants import PREFIXES


def rdf_file_to_graph(
    graph: Graph,
    filepath: Path,
    base_prefix: str | None = None,
    base_namespace: Namespace | None = None,
    prefixes: dict[str, Namespace] = PREFIXES,
) -> Graph:
    """Created rdflib Graph instance loaded with RDF triples from file

    Args:
        filepath: Path to the RDF file
        base_prefix: base prefix for URIs. Defaults to None.
        base_namespace: base namespace for URIs . Defaults to None.
        prefixes: Dictionary of prefixes to bind to graph. Defaults to PREFIXES.
        graph: Graph instance to load RDF triples into. Defaults to None.

    Returns:
        Graph instance loaded with RDF triples from file
    """

    if filepath.is_file():
        graph.parse(filepath, publicID=base_namespace)
    else:
        for filename in filepath.iterdir():
            if filename.is_file():
                graph.parse(filename, publicID=base_namespace)
    if base_prefix and base_namespace:
        graph.bind(base_prefix, base_namespace)
    if prefixes:
        for prefix, namespace in prefixes.items():
            graph.bind(prefix, namespace)

    return graph
