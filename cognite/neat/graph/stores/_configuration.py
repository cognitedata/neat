import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

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
    file_path: str | None = None
    query_url: str | None = None
    update_url: str | None = None
    user: str | None = None
    password: str | None = None
    api_root_url: str = "http://localhost:7200"
