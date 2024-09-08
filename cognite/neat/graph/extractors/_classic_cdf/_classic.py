from collections import defaultdict
from collections.abc import Iterable

from cognite.client import CogniteClient
from rdflib import RDF, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple

from ._assets import AssetsExtractor
from ._base import Prefix, _ClassicCDFBaseExtractor
from ._data_sets import DataSetExtractor
from ._events import EventsExtractor
from ._files import FilesExtractor
from ._labels import LabelsExtractor
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
        progress_bar: bool = False,
    ):
        self._client = client
        if sum([bool(data_set_external_id), bool(root_asset_external_id)]) != 1:
            raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")
        self._root_asset_external_id = root_asset_external_id
        self._data_set_external_id = data_set_external_id
        self._namespace = namespace or DEFAULT_NAMESPACE
        self._progress_bar = progress_bar

        self._resource_ids_by_type: dict[str, set[int]] = defaultdict(set)
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

        label_iterator = self._client.labels.retrieve(external_id=list(self._labels), ignore_unknown_ids=True)
        yield from LabelsExtractor(label_iterator, self._namespace, total=len(label_iterator)).extract()
        data_set_iterator = self._client.data_sets.retrieve_multiple(ids=list(self._data_set_ids))
        yield from DataSetExtractor(
            data_set_iterator, self._namespace, total=len(data_set_iterator), unpack_metadata=False
        ).extract()

    def _extract_subextractor(
        self, extractor: _ClassicCDFBaseExtractor, resource_type: str | None = None
    ) -> Iterable[Triple]:
        for triple in extractor.extract():
            if triple[1] == RDF.type and resource_type is not None:
                self._resource_ids_by_type[resource_type].add(int(triple[0].removeprefix(resource_type)))
            elif triple[1] == self._namespace.label:
                self._labels.add(triple[2].removeprefix(Prefix.label))
            elif triple[1] == self._namespace.dataset:
                self._data_set_ids.add(int(triple[2].removeprefix(Prefix.data_set)))
            yield triple
