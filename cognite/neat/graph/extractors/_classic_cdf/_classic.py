from collections import defaultdict
from collections.abc import Iterable

from cognite.client import CogniteClient
from rdflib import Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.collection_ import chunker
from cognite.neat.utils.rdf_ import remove_namespace_from_uri

from ._assets import AssetsExtractor
from ._base import Prefix, _ClassicCDFBaseExtractor
from ._data_sets import DataSetExtractor
from ._events import EventsExtractor
from ._files import FilesExtractor
from ._labels import LabelsExtractor
from ._relationships import RelationshipsExtractor
from ._sequences import SequencesExtractor
from ._timeseries import TimeSeriesExtractor


class ClassicExtractor(BaseExtractor):
    """This extractor extracts all classic CDF Resources."""

    def __init__(
        self,
        client: CogniteClient,
        data_set_external_id: str | None = None,
        root_asset_external_id: str | None = None,
        namespace: Namespace | None = None,
    ):
        self._client = client
        if sum([bool(data_set_external_id), bool(root_asset_external_id)]) != 1:
            raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")
        self._root_asset_external_id = root_asset_external_id
        self._data_set_external_id = data_set_external_id
        self._namespace = namespace or DEFAULT_NAMESPACE

        self._resource_external_ids_by_type: dict[str, set[str]] = defaultdict(set)
        self._labels: set[str] = set()
        self._data_set_ids: set[int] = set()

    def extract(self) -> Iterable[Triple]:
        """Extracts all classic CDF Resources."""
        extractor: AssetsExtractor | TimeSeriesExtractor | SequencesExtractor | EventsExtractor | FilesExtractor
        for extractor, resource_type in [  # type: ignore[assignment]
            (AssetsExtractor, Prefix.asset),
            (TimeSeriesExtractor, Prefix.time_series),
            (SequencesExtractor, Prefix.sequence),
            (EventsExtractor, Prefix.event),
            (FilesExtractor, Prefix.file),
        ]:
            if self._data_set_external_id:
                extractor = extractor.from_dataset(
                    self._client, self._data_set_external_id, self._namespace, unpack_metadata=False
                )
            elif self._root_asset_external_id:
                extractor = extractor.from_hierarchy(
                    self._client, self._root_asset_external_id, self._namespace, unpack_metadata=False
                )
            else:
                raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")

            yield from self._extract_subextractor(extractor, resource_type)

        for resource_type, source_external_ids in self._resource_external_ids_by_type.items():
            for chunk in chunker(list(source_external_ids), chunk_size=1000):
                relationship_iterator = self._client.relationships(
                    source_external_ids=list(chunk), source_types=[resource_type.removesuffix("_")]
                )
                yield from RelationshipsExtractor(
                    relationship_iterator, self._namespace, unpack_metadata=False
                ).extract()

        label_iterator = self._client.labels.retrieve(external_id=list(self._labels), ignore_unknown_ids=True)
        yield from LabelsExtractor(label_iterator, self._namespace, total=len(label_iterator)).extract()
        data_set_iterator = self._client.data_sets.retrieve_multiple(ids=list(self._data_set_ids))
        yield from DataSetExtractor(
            data_set_iterator, self._namespace, total=len(data_set_iterator), unpack_metadata=False
        ).extract()

    def _extract_subextractor(self, extractor: _ClassicCDFBaseExtractor, resource_type: str) -> Iterable[Triple]:
        for triple in extractor.extract():
            if triple[1] == self._namespace.external_id:
                self._resource_external_ids_by_type[resource_type].add(remove_namespace_from_uri(triple[2]))
            elif triple[1] == self._namespace.label:
                self._labels.add(remove_namespace_from_uri(triple[2]).removeprefix(Prefix.label))
            elif triple[1] == self._namespace.dataset:
                self._data_set_ids.add(int(remove_namespace_from_uri(triple[2]).removeprefix(Prefix.data_set)))
            yield triple
