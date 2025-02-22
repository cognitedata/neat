import urllib.parse
from collections.abc import Iterable, Set
from typing import Any, cast

from cognite.client.data_classes import Row, RowList
from rdflib import RDF, Namespace, URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_RAW_URI
from cognite.neat._shared import Triple

from ._base import BaseExtractor
from ._dict import DEFAULT_EMPTY_VALUES, DictExtractor


class RAWExtractor(BaseExtractor):
    def __init__(
        self,
        client: NeatClient,
        db_name: str,
        table_name: str,
        table_type: str | None = None,
        namespace: Namespace | None = None,
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        unpack_json: bool = False,
    ) -> None:
        self.client = client
        self.db_name = db_name
        self.table_name = table_name
        self.table_type = table_type
        self.namespace = namespace or Namespace(DEFAULT_RAW_URI.format(db=db_name))
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.unpack_json = unpack_json

    @property
    def _rdf_type(self) -> URIRef:
        return self.namespace[urllib.parse.quote(self.table_type or self.table_name)]

    def extract(self) -> Iterable[Triple]:
        for row in self.client.raw.rows(self.db_name, self.table_name, partitions=10, chunk_size=None):
            if isinstance(row, Row):
                yield from self._row2triples(row)
            elif isinstance(row, RowList):
                # Bug in SDK returning row list with chunk_size= None
                for item in row:
                    yield from self._row2triples(item)

    def _row2triples(self, row: Row) -> Iterable[Triple]:
        # The row is always set. It is just the PySDK that have it as str | None
        key, data = cast(tuple[str, dict[str, Any]], (row.key, row.columns))
        identifier = self.namespace[urllib.parse.quote(key)]
        yield identifier, RDF.type, self._rdf_type

        yield from DictExtractor(
            identifier, data, self.namespace, self.empty_values, self.str_to_ideal_type, self.unpack_json
        ).extract()
