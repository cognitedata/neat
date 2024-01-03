from ._base import NeatGraphStoreBase
from ._graphdb_store import GraphDBStore
from ._memory_store import MemoryStore
from ._oxigraph_store import OxiGraphStore

STORE_BY_TYPE: dict[str, type[NeatGraphStoreBase]] = {
    store.rdf_store_type: store for store in NeatGraphStoreBase.__subclasses__()  # type: ignore[type-abstract]
}
STORE_BY_TYPE["sparql"] = MemoryStore
AVAILABLE_STORES = set(STORE_BY_TYPE.keys())

__all__ = ["NeatGraphStoreBase", "MemoryStore", "OxiGraphStore", "GraphDBStore", "STORE_BY_TYPE", "AVAILABLE_STORES"]
