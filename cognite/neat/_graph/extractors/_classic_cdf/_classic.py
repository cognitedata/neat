import typing
import urllib.parse
import warnings
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import ClassVar, NamedTuple, cast

from cognite.client import CogniteClient
from cognite.client.exceptions import CogniteAPIError
from rdflib import Namespace, URIRef

from cognite.neat._constants import CLASSIC_CDF_NAMESPACE, DEFAULT_NAMESPACE, get_default_prefixes_and_namespaces
from cognite.neat._graph.extractors._base import KnowledgeGraphExtractor
from cognite.neat._issues.errors import NeatValueError, ResourceNotFoundError
from cognite.neat._issues.warnings import CDFAuthWarning, NeatValueWarning
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.catalog import classic_model
from cognite.neat._rules.models import InformationInputRules, InformationRules
from cognite.neat._rules.models._rdfpath import Entity as RDFPathEntity
from cognite.neat._rules.models._rdfpath import RDFPath, SingleProperty
from cognite.neat._shared import Triple
from cognite.neat._utils.collection_ import chunker, iterate_progress_bar
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.text import to_snake

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


class ClassicGraphExtractor(KnowledgeGraphExtractor):
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
        limit_per_type: int | None = None,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
    ):
        self._client = client
        if sum([bool(data_set_external_id), bool(root_asset_external_id)]) != 1:
            raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")
        self._root_asset_external_id = root_asset_external_id
        self._data_set_external_id = data_set_external_id
        self._namespace = namespace or CLASSIC_CDF_NAMESPACE
        self._extractor_args = dict(
            namespace=self._namespace,
            unpack_metadata=False,
            as_write=True,
            camel_case=True,
            limit=limit_per_type,
            prefix=prefix,
            identifier=identifier,
        )
        self._identifier = identifier
        self._prefix = prefix
        self._limit_per_type = limit_per_type

        self._uris_by_external_id_by_type: dict[InstanceIdPrefix, dict[str, URIRef]] = defaultdict(dict)
        self._source_external_ids_by_type: dict[InstanceIdPrefix, set[str]] = defaultdict(set)
        self._target_external_ids_by_type: dict[InstanceIdPrefix, set[str]] = defaultdict(set)
        self._relationship_subject_predicate_type_external_id: list[tuple[URIRef, URIRef, str, str]] = []
        self._labels: set[str] = set()
        self._data_set_ids: set[int] = set()
        self._data_set_external_ids: set[str] = set()
        self._extracted_labels = False
        self._extracted_data_sets = False
        self._asset_external_ids_by_id: dict[int, str] = {}
        self._dataset_external_ids_by_id: dict[int, str] = {}

    def _get_activity_names(self) -> list[str]:
        activities = [data_access_object.extractor_cls.__name__ for data_access_object in self._classic_node_types] + [
            RelationshipsExtractor.__name__,
        ]
        if self._extracted_labels:
            activities.append(LabelsExtractor.__name__)
        if self._extracted_data_sets:
            activities.append(DataSetExtractor.__name__)
        return activities

    def extract(self) -> Iterable[Triple]:
        """Extracts all classic CDF Resources."""
        self._validate_exists()

        yield from self._extract_core_start_nodes()

        yield from self._extract_start_node_relationships()

        yield from self._extract_core_end_nodes()

        if self._identifier == "id":
            yield from self._extract_relationship_target_triples()

        try:
            yield from self._extract_labels()
        except CogniteAPIError as e:
            warnings.warn(CDFAuthWarning("extract labels", str(e)), stacklevel=2)
        else:
            self._extracted_labels = True

        try:
            yield from self._extract_data_sets()
        except CogniteAPIError as e:
            warnings.warn(CDFAuthWarning("extract data sets", str(e)), stacklevel=2)
        else:
            self._extracted_data_sets = True

    def get_information_rules(self) -> InformationRules:
        # To avoid circular imports
        from cognite.neat._rules.importers import ExcelImporter

        unverified = cast(ReadRules[InformationInputRules], ExcelImporter(classic_model).to_rules())
        if unverified.rules is None:
            raise NeatValueError(f"Could not read the classic model rules from {classic_model}.")

        verified = unverified.rules.as_verified_rules()
        prefixes = get_default_prefixes_and_namespaces()
        instance_prefix: str | None = next((k for k, v in prefixes.items() if v == self._namespace), None)
        if instance_prefix is None:
            # We need to add a new prefix
            instance_prefix = f"prefix_{len(prefixes) + 1}"
            prefixes[instance_prefix] = self._namespace
        verified.prefixes = prefixes

        is_snake_case = self._extractor_args["camel_case"] is False
        for prop in verified.properties:
            prop_id = prop.property_
            if is_snake_case:
                prop_id = to_snake(prop_id)
            prop.instance_source = RDFPath(
                traversal=SingleProperty(
                    class_=RDFPathEntity(prefix=instance_prefix, suffix=prop.class_.suffix),
                    property=RDFPathEntity(prefix=instance_prefix, suffix=prop_id),
                )
            )
        return verified

    @property
    def description(self) -> str:
        if self._data_set_external_id:
            source = f"data set {self._data_set_external_id}."
        elif self._root_asset_external_id:
            source = f"root asset {self._root_asset_external_id}."
        else:
            source = "unknown source."
        return f"Extracting clasic CDF Graph (Assets, TimeSeries, Sequences, Events, Files) from {source}."

    @property
    def source_uri(self) -> URIRef:
        if self._data_set_external_id:
            resource = "dataset"
            external_id = self._data_set_external_id
        elif self._root_asset_external_id:
            resource = "asset"
            external_id = self._root_asset_external_id
        else:
            resource = "unknown"
            external_id = "unknown"
        return DEFAULT_NAMESPACE[f"{self._client.config.project}/{resource}/{urllib.parse.quote(external_id)}"]

    def _validate_exists(self) -> None:
        if self._data_set_external_id:
            if self._client.data_sets.retrieve(external_id=self._data_set_external_id) is None:
                raise ResourceNotFoundError(self._data_set_external_id, "data set")
        elif self._root_asset_external_id:
            if self._client.assets.retrieve(external_id=self._root_asset_external_id) is None:
                raise ResourceNotFoundError(self._root_asset_external_id, "root asset")
        else:
            raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")

    def _extract_core_start_nodes(self):
        for core_node in self._classic_node_types:
            if self._data_set_external_id:
                extractor = core_node.extractor_cls.from_dataset(
                    self._client, self._data_set_external_id, **self._extractor_args
                )
            elif self._root_asset_external_id:
                extractor = core_node.extractor_cls.from_hierarchy(
                    self._client, self._root_asset_external_id, **self._extractor_args
                )
            else:
                raise ValueError("Exactly one of data_set_external_id or root_asset_external_id must be set.")

            if self._identifier == "externalId":
                if isinstance(extractor, AssetsExtractor):
                    self._asset_external_ids_by_id = extractor.asset_external_ids_by_id
                else:
                    extractor.asset_external_ids_by_id = self._asset_external_ids_by_id
                extractor.lookup_dataset_external_id = self._lookup_dataset
            elif self._identifier == "id":
                extractor._log_urirefs = True

            yield from self._extract_with_logging_label_dataset(extractor, core_node.resource_type)

            if self._identifier == "id":
                self._uris_by_external_id_by_type[core_node.resource_type].update(extractor._uriref_by_external_id)

    def _extract_start_node_relationships(self):
        for start_resource_type, source_external_ids in self._source_external_ids_by_type.items():
            start_type = start_resource_type.removesuffix("_")
            for chunk in self._chunk(list(source_external_ids), description=f"Extracting {start_type} relationships"):
                relationship_iterator = self._client.relationships(
                    source_external_ids=list(chunk), source_types=[start_type]
                )
                extractor = RelationshipsExtractor(relationship_iterator, **self._extractor_args)
                # This is a private attribute, but we need to set it to log the target nodes.
                extractor._log_target_nodes = True
                if self._identifier == "id":
                    extractor._uri_by_external_id_by_by_type = self._uris_by_external_id_by_type

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

                if self._identifier == "id":
                    # We need to store all future target triples which we will lookup after fetching
                    # the target nodes.
                    self._relationship_subject_predicate_type_external_id.extend(extractor._target_triples)

    def _extract_core_end_nodes(self):
        for core_node in self._classic_node_types:
            target_external_ids = self._target_external_ids_by_type[core_node.resource_type]
            api = getattr(self._client, core_node.api_name)
            for chunk in self._chunk(
                list(target_external_ids),
                description=f"Extracting end nodes {core_node.resource_type.removesuffix('_')}",
            ):
                resource_iterator = api.retrieve_multiple(external_ids=list(chunk), ignore_unknown_ids=True)
                extractor = core_node.extractor_cls(resource_iterator, **self._extractor_args)

                extractor.asset_external_ids_by_id = self._asset_external_ids_by_id
                extractor.lookup_dataset_external_id = self._lookup_dataset
                if self._identifier == "id":
                    extractor._log_urirefs = True

                yield from self._extract_with_logging_label_dataset(extractor)

                if self._identifier == "id":
                    self._uris_by_external_id_by_type[core_node.resource_type].update(extractor._uriref_by_external_id)

    def _extract_relationship_target_triples(self):
        for id_, predicate, type_, external_id in self._relationship_subject_predicate_type_external_id:
            try:
                object_uri = self._uris_by_external_id_by_type[InstanceIdPrefix.from_str(type_)][external_id]
            except KeyError:
                warnings.warn(NeatValueWarning(f"Missing externalId {external_id} for {type_}"), stacklevel=2)
            else:
                yield id_, predicate, object_uri

    def _extract_labels(self):
        for chunk in self._chunk(list(self._labels), description="Extracting labels"):
            label_iterator = self._client.labels.retrieve(external_id=list(chunk), ignore_unknown_ids=True)
            yield from LabelsExtractor(label_iterator, **self._extractor_args).extract()

    def _extract_data_sets(self):
        for chunk in self._chunk(list(self._data_set_ids), description="Extracting data sets"):
            data_set_iterator = self._client.data_sets.retrieve_multiple(ids=list(chunk), ignore_unknown_ids=True)
            yield from DataSetExtractor(data_set_iterator, **self._extractor_args).extract()
        for chunk in self._chunk(list(self._data_set_external_ids), description="Extracting data sets"):
            data_set_iterator = self._client.data_sets.retrieve_multiple(
                external_ids=list(chunk), ignore_unknown_ids=True
            )
            yield from DataSetExtractor(data_set_iterator, **self._extractor_args).extract()

    def _extract_with_logging_label_dataset(
        self, extractor: ClassicCDFBaseExtractor, resource_type: InstanceIdPrefix | None = None
    ) -> Iterable[Triple]:
        for triple in extractor.extract():
            if triple[1] == self._namespace.externalId and resource_type is not None:
                self._source_external_ids_by_type[resource_type].add(remove_namespace_from_uri(triple[2]))
            elif triple[1] == self._namespace.labels:
                self._labels.add(remove_namespace_from_uri(triple[2]).removeprefix(InstanceIdPrefix.label))
            elif triple[1] == self._namespace.dataSetId:
                identifier = remove_namespace_from_uri(triple[2]).removeprefix(InstanceIdPrefix.data_set)
                try:
                    self._data_set_ids.add(int(identifier))
                except ValueError:
                    self._data_set_external_ids.add(identifier)
            yield triple

    @staticmethod
    def _chunk(items: Sequence, description: str) -> Iterable:
        to_iterate: Iterable = chunker(items, chunk_size=1000)
        if items:
            return iterate_progress_bar(to_iterate, (len(items) // 1_000) + 1, description)
        else:
            return to_iterate

    def _lookup_dataset(self, dataset_id: int) -> str:
        if dataset_id not in self._dataset_external_ids_by_id:
            try:
                if (dataset := self._client.data_sets.retrieve(id=dataset_id)) and dataset.external_id:
                    self._dataset_external_ids_by_id[dataset_id] = dataset.external_id
                else:
                    raise KeyError(f"Could not find dataset with id {dataset_id}.")
            except CogniteAPIError as e:
                warnings.warn(CDFAuthWarning("lookup dataset", str(e)), stacklevel=2)
                return f"{InstanceIdPrefix.data_set}{dataset_id}"
        return self._dataset_external_ids_by_id[dataset_id]
