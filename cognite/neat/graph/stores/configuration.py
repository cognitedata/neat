from enum import StrEnum

from pydantic import BaseModel


class RdfStoreType(StrEnum):
    """RDF Store type"""

    MEMORY = "memory"
    FILE = "file"
    GRAPHDB = "graphdb"
    SPARQL = "sparql"
    OXIGRAPH = "oxigraph"


class RdfStoreConfig(BaseModel):
    type: RdfStoreType
    file_path: str = None
    query_url: str = None
    update_url: str = None
    user: str = None
    password: str = None
    api_root_url: str = "http://localhost:7200"
