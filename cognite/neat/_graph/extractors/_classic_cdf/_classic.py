from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import ClassVar, NamedTuple

from cognite.client import CogniteClient
from rdflib import Namespace

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors._base import BaseExtractor
from cognite.neat._graph.models import Triple
from cognite.neat._utils.collection_ import chunker
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._assets import AssetsExtractor
from ._base import ClassicCDFBaseExtractor, InstanceIdPrefix
from ._data_sets import DataSetExtractor
from ._events import EventsExtractor
from ._files import FilesExtractor
from ._labels import LabelsExtractor
from ._relationships import RelationshipsExtractor
from ._sequences import SequencesExtractor
from ._timeseries import TimeSeriesExtractor


class _ClassicCoreType(NamedTuple):
    extractor_cls: (
        type[AssetsExtractor]
        | type[TimeSeriesExtractor]
        | type[SequencesExtractor]
        | type[EventsExtractor]
        | type[FilesExtractor]
    )
    resource_type: InstanceIdPrefix
    api_name: str


class ClassicGraphExtractor(BaseExtractor):
    """This extractor extracts all classic CDF Resources.

    The Classic Graph consists of the following core resource type.

    Classic Node CDF Resources:
     - Assets
     - TimeSeries
     - Sequences
     - Events
     - Files

    All the classic node CDF resources can have one or more connections to one or more assets. This
    will match a direct relationship in the data modeling of CDF.

    In addition, you have relationships between the classic node CDF resources. This matches an edge
    in the data modeling of CDF.

    Finally, you have labels and data sets that to organize the graph. In which data sets have a similar,
    but different, role as a space in data modeling. While labels can be compared to node types in data modeling,
    used to quickly filter and find nodes/edges.

    This extractor will extract the classic CDF graph into Neat starting from either a data set or a root asset.

    It works as follows:

    1. Extract all core nodes (assets, time series, sequences, events, files) filtered by the given data set or
       root asset.
    2. Extract all relationships starting from any of the extracted core nodes.
    3. Extract all core nodes that are targets of the relationships that are not already extracted.
    4. Extract all labels that are connected to the extracted core nodes/relationships.
    5. Extract all data sets that are connected to the extracted core nodes/relationships.

    Args:
        client (CogniteClient): The Cognite client to use.
        data_set_external_id (str, optional): The data set external id to extract from. Defaults to None.
        root_asset_external_id (str, optional): The root asset external id to extract from. Defaults to None.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
    """

    # These are the core resource types in the classic CDF.
    _classic_node_types: ClassVar[tuple[_ClassicCoreType, ...]] = (
        _ClassicCoreType(AssetsExtractor, InstanceIdPrefix.asset, "assets"),
        _ClassicCoreType(TimeSeriesExtractor, InstanceIdPrefix.time_series, "time_series"),
        _ClassicCoreType(SequencesExtractor, InstanceIdPrefix.sequence, "sequences"),
        _ClassicCoreType(EventsExtractor, InstanceIdPrefix.event, "events"),
        _ClassicCoreType(FilesExtractor, InstanceIdPrefix.file, "files"),
    )

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

        self._source_external_ids_by_type: dict[InstanceIdPrefix, set[str]] = defaultdict(set)
        self._target_external_ids_by_type: dict[InstanceIdPrefix, set[str]] = defaultdict(set)
        self._labels: set[str] = set()
        self._data_set_ids: set[int] = set()

    def extract(self) -> Iterable[Triple]:
        """Extracts all classic CDF Resources."""
        yield from self._extract_core_start_nodes()

        yield from self._extract_start_node_relationships()

        yield from self._extract_core_end_nodes()

        yield from self._extract_labels()
        yield from self._extract_data_sets()

    def _extract_core_start_nodes(self):
        for core_node in self._classic_node_types:
            if self._data_set_external_id:
                extractor = core_node.extractor_cls.from_dataset(
                    self._client, self._data_set_external_id, self._namespace, unpack_metadata=False
                )
            elif self._root_asset_external_id:
                extractor = core_node.extractor_cls.from_hierarchy(
                    self._client, self._root_asset_external_id, self._namespace, unpack_metadata=False
                )
            else:
                raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")

            yield from self._extract_with_logging_label_dataset(extractor, core_node.resource_type)

    def _extract_start_node_relationships(self):
        for start_resource_type, source_external_ids in self._source_external_ids_by_type.items():
            start_type = start_resource_type.removesuffix("_")
            for chunk in self._chunk(list(source_external_ids), description=f"Extracting {start_type} relationships"):
                relationship_iterator = self._client.relationships(
                    source_external_ids=list(chunk), source_types=[start_type]
                )
                extractor = RelationshipsExtractor(relationship_iterator, self._namespace, unpack_metadata=False)
                # This is a private attribute, but we need to set it to log the target nodes.
                extractor._log_target_nodes = True

                yield from extractor.extract()

                # After the extraction is done, we need to update all the new target nodes so
                # we can extract them in the next step.
                for end_type, target_external_ids in extractor._target_external_ids_by_type.items():
                    for external_id in target_external_ids:
                        # We only want to extract the target nodes that are not already extracted.
                        # Even though _source_external_ids_by_type is a defaultdict, we have to check if the key exists.
                        # This is because we might not have extracted any nodes of that type yet, and looking up
                        # a key that does not exist will create it. We are iterating of this dictionary, and
                        # we do not want to create new keys while iterating.
                        if (
                            end_type not in self._source_external_ids_by_type
                            or external_id not in self._source_external_ids_by_type[end_type]
                        ):
                            self._target_external_ids_by_type[end_type].add(external_id)

    def _extract_core_end_nodes(self):
        for core_node in self._classic_node_types:
            target_external_ids = self._target_external_ids_by_type[core_node.resource_type]
            api = getattr(self._client, core_node.api_name)
            for chunk in self._chunk(
                list(target_external_ids),
                description=f"Extracting end nodes {core_node.resource_type.removesuffix('_')}",
            ):
                resource_iterator = api.retrieve_multiple(external_ids=list(chunk), ignore_unknown_ids=True)
                extractor = core_node.extractor_cls(resource_iterator, self._namespace, unpack_metadata=False)
                yield from self._extract_with_logging_label_dataset(extractor)

    def _extract_labels(self):
        for chunk in self._chunk(list(self._labels), description="Extracting labels"):
            label_iterator = self._client.labels.retrieve(external_id=list(chunk), ignore_unknown_ids=True)
            yield from LabelsExtractor(label_iterator, self._namespace).extract()

    def _extract_data_sets(self):
        for chunk in self._chunk(list(self._data_set_ids), description="Extracting data sets"):
            data_set_iterator = self._client.data_sets.retrieve_multiple(ids=list(chunk), ignore_unknown_ids=True)
            yield from DataSetExtractor(data_set_iterator, self._namespace, unpack_metadata=False).extract()

    def _extract_with_logging_label_dataset(
        self, extractor: ClassicCDFBaseExtractor, resource_type: InstanceIdPrefix | None = None
    ) -> Iterable[Triple]:
        for triple in extractor.extract():
            if triple[1] == self._namespace.external_id and resource_type is not None:
                self._source_external_ids_by_type[resource_type].add(remove_namespace_from_uri(triple[2]))
            elif triple[1] == self._namespace.label:
                self._labels.add(remove_namespace_from_uri(triple[2]).removeprefix(InstanceIdPrefix.label))
            elif triple[1] == self._namespace.dataset:
                self._data_set_ids.add(
                    int(remove_namespace_from_uri(triple[2]).removeprefix(InstanceIdPrefix.data_set))
                )
            yield triple

    @staticmethod
    def _chunk(items: Sequence, description: str) -> Iterable:
        to_iterate: Iterable = chunker(items, chunk_size=1000)
        try:
            from rich.progress import track
        except ModuleNotFoundError:
            ...
        else:
            to_iterate = track(
                to_iterate,
                total=(len(items) // 1000) + 1,
                description=description,
            )
        return to_iterate
