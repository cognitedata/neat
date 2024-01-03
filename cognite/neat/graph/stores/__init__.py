from ._base import NeatGraphStoreBase
from ._configuration import RdfStoreConfig, RdfStoreType
from ._graphdb_store import GraphDBStore
from ._memory_store import MemoryStore
from ._oxigraph_store import OxiGraphStore
from ._rdf_to_graph import rdf_file_to_graph

STORE_BY_TYPE: dict[str, type[NeatGraphStoreBase]] = {
    store.rdf_store_type: store for store in NeatGraphStoreBase.__subclasses__()  # type: ignore[type-abstract]
}

AVAILABLE_STORES = set(STORE_BY_TYPE.keys())

__all__ = [
    "NeatGraphStoreBase",
    "MemoryStore",
    "OxiGraphStore",
    "GraphDBStore",
    "STORE_BY_TYPE",
    "AVAILABLE_STORES",
    "RdfStoreType",
    "RdfStoreConfig",
    "rdf_file_to_graph",
]
