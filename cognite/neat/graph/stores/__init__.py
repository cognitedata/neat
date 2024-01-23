from ._base import NeatGraphStoreBase
from ._graphdb_store import GraphDBStore
from ._memory_store import MemoryStore
from ._oxigraph_store import OxiGraphStore

STORE_BY_TYPE: dict[str, type[NeatGraphStoreBase]] = {}
for store in NeatGraphStoreBase.__subclasses__():
    STORE_BY_TYPE[store.rdf_store_type] = store  # type: ignore[type-abstract]

del store  # Cleanup namespace
AVAILABLE_STORES = set(STORE_BY_TYPE.keys())

__all__ = ["NeatGraphStoreBase", "MemoryStore", "OxiGraphStore", "GraphDBStore", "STORE_BY_TYPE", "AVAILABLE_STORES"]
