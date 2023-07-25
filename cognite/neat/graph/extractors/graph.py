from pathlib import Path

from rdflib import Graph, Namespace

from cognite.neat.app.api.configuration import DEFAULT_NAMESPACE, DEFAULT_URI, PREFIXES

__all__ = ["rdf_file_to_graph"]


def rdf_file_to_graph(
    filepath: Path,
    base_prefix: str = DEFAULT_URI,
    base_namespace: Namespace = DEFAULT_NAMESPACE,
    prefixes: dict[str, Namespace] = PREFIXES,
) -> Graph:
    """Loads RDF from file

    Parameters
    ----------
    filepath : Path
        File path to RDF
    namespace : Namespace, optional
        The logical URI to use as the graph namespace base, by default "http://purl.org/cognite/app-dm"
    prefixes : dict, optional
        Dictionary containing prefix-namespace pairs, by default PREFIXES

    Returns
    -------
    Graph
        An RDF Graph
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
