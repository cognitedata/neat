import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import yaml
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability, DataModelsAcl
from rdflib import URIRef

from cognite.neat._client import NeatClient
from cognite.neat._client._api.data_modeling_loaders import MultiCogniteAPIError
from cognite.neat._issues import IssueList, NeatIssue
from cognite.neat._issues.errors import ResourceCreationError, ResourceNotFoundError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.collection_ import iterate_progress_bar_if_above_config_threshold
from cognite.neat._utils.rdf_ import namespace_as_space, remove_namespace_from_uri, split_uri
from cognite.neat._utils.text import NamingStandardization
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, _START_OF_CLASS, CDFLoader


class InstanceSpaceLoader(CDFLoader[dm.SpaceApply]):
    """Loads Instance Space into Cognite Data Fusion (CDF).

    This class also exposes the `space_by_instance_uri` method used by
    the DMSLoader to lookup space for each instance URI.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data from.
        instance_space (str): The instance space to load the data into.
        space_property (str): The property to use to determine the space for each instance.
        use_source_space (bool): If True, use the source space of the instances when extracted from CDF.
        neat_prefix_by_predicate_uri (dict[URIRef, str] | None): A dictionary that maps a predicate URIRef to a
            prefix that Neat added to the object upon extraction. This is used to remove the prefix from the
            object before creating the instance.
    """

    def __init__(
        self,
        graph_store: NeatGraphStore | None = None,
        instance_space: str | None = None,
        space_property: str | None = None,
        use_source_space: bool = False,
        neat_prefix_by_predicate_uri: dict[URIRef, str] | None = None,
    ) -> None:
        self.graph_store = graph_store
        self.instance_space = instance_space
        self.space_property = space_property
        self.use_source_space = use_source_space
        self.neat_prefix_by_predicate_uri = neat_prefix_by_predicate_uri or {}

        self._lookup_issues = IssueList()

        self._has_looked_up = False
        self._space_by_instance_uri: dict[URIRef, str] = {}

    @property
    def space_by_instance_uri(self) -> dict[URIRef, str]:
        """Returns a dictionary mapping instance URIs to their respective spaces."""
        if not self._has_looked_up:
            self._lookup_spaces()
            self._has_looked_up = True
        return self._space_by_instance_uri

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            DataModelsAcl(
                actions=[
                    DataModelsAcl.Action.Write,
                    DataModelsAcl.Action.Read,
                ],
                scope=DataModelsAcl.Scope.All(),
            )
        ]

    def _upload_to_cdf(
        self,
        client: NeatClient,
        items: list[dm.SpaceApply],
        dry_run: bool,
        read_issues: IssueList,
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        cdf_items = client.data_modeling.spaces.retrieve([item.space for item in items])
        cdf_idem_by_id = {item.space: item for item in cdf_items}

        to_create = dm.SpaceApplyList([])
        to_update = dm.SpaceApplyList([])
        unchanged = dm.SpaceApplyList([])

        for local_space in items:
            cdf_space = cdf_idem_by_id.get(local_space.space)
            if cdf_space is None:
                to_create.append(local_space)
            elif cdf_space != local_space.as_write():
                to_update.append(local_space)
            else:
                unchanged.append(local_space)
        loader = client.loaders.spaces
        results: UploadResult[str] = UploadResult(class_name or loader.resource_name)
        results.unchanged.update(unchanged.as_ids())
        if dry_run:
            results.created.update(to_create.as_ids())
            results.changed.update(to_update.as_ids())
            yield results
        if to_create:
            try:
                client.loaders.spaces.create(to_create)
            except MultiCogniteAPIError as e:
                results.failed_created.update(to_create.as_ids())
                for error in e.errors:
                    results.error_messages.append(f"Failed to create {loader.resource_name}: {error!s}")
            else:
                results.created.update(to_create.as_ids())

        if to_update:
            try:
                client.loaders.spaces.update(to_update)
            except MultiCogniteAPIError as e:
                results.failed_changed.update(to_update.as_ids())
                for error in e.errors:
                    results.error_messages.append(f"Failed to update {loader.resource_name}: {error!s}")
            else:
                results.changed.update(to_update.as_ids())

        yield results

    def write_to_file(self, filepath: Path) -> None:
        """Dumps the instance spaces to file."""
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"spaces": [], "issues": []}
        for item in self.load(stop_on_exception=False):
            key = {
                dm.SpaceApply: "spaces",
                NeatIssue: "issues",
            }.get(type(item))
            if key is None:
                # This should never happen, and is a bug in neat
                raise ValueError(f"Item {item} is not supported. This is a bug in neat please report it.")
            dumped[key].append(item.dump())
        with filepath.open("w", encoding=self._encoding, newline=self._new_line) as f:
            if filepath.suffix == ".json":
                json.dump(dumped, f, indent=2)
            else:
                yaml.safe_dump(dumped, f, sort_keys=False)

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dm.SpaceApply | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        yield from self._lookup_issues
        seen: set[str] = set()
        for space_str in self.space_by_instance_uri.values():
            if space_str in seen:
                continue
            yield dm.SpaceApply(space=space_str)
            seen.add(space_str)

    def _lookup_spaces(self) -> None:
        # Case 1: Same instance space for all instances:
        if isinstance(self.instance_space, str) and self.space_property is None:
            self._space_by_instance_uri = defaultdict(lambda: cast(str, self.instance_space))
            # Adding a dummy entry to ensure that the instance space is included
            self._space_by_instance_uri[URIRef(self.instance_space)] = self.instance_space
            return
        if self.graph_store is None:
            raise ValueError("Graph store must be provided to lookup spaces")
        # Case 2: Use the source space, i.e., the space of the instances when extracted from CDF
        if self.use_source_space:
            self._lookup_instance_uris(self.graph_store)
        # Case 3: Use a property on each instance to determine the space.
        elif self.space_property is not None:
            if self.instance_space is None:
                raise ValueError(
                    f"Missing fallback instance space. This is required when using '{self.space_property=}'"
                )
            self._space_by_instance_uri = defaultdict(lambda: cast(str, self.instance_space))
            self._lookup_space_property(self.graph_store, self.space_property)
        else:
            raise ValueError("Either 'instance_space", "space_property', or 'use_source_space' must be provided. ")

    def _lookup_instance_uris(self, graph_store: NeatGraphStore) -> None:
        for class_uri, instance_uri in graph_store.queries.select.list_instances_ids():
            namespace, external_id = split_uri(instance_uri)
            space = namespace_as_space(namespace)
            if space is None:
                instance_type = remove_namespace_from_uri(class_uri)
                error = ResourceCreationError(
                    instance_uri, instance_type, f"Could not find space for {instance_uri!s}."
                )
                self._lookup_issues.append(error)
            else:
                self._space_by_instance_uri[instance_uri] = space

    def _lookup_space_property(self, graph_store: NeatGraphStore, space_property: str) -> None:
        properties_by_uriref = graph_store.queries.select.properties()
        space_property_uri = next((k for k, v in properties_by_uriref.items() if v == space_property), None)
        if space_property_uri is None:
            error: ResourceNotFoundError[str, str] = ResourceNotFoundError(
                self.space_property,
                "property",
                more=f"Could not find the {space_property} in the graph.",
            )
            self._lookup_issues.append(error)
            return

        class_with_total_pair = graph_store.queries.select.summarize_instances()
        total = sum([count for _, count in class_with_total_pair])
        instance_iterable = graph_store.queries.select.list_instances_ids_by_space(space_property_uri)
        instance_iterable = iterate_progress_bar_if_above_config_threshold(
            instance_iterable, total, f"Looking up spaces for {total} instances..."
        )
        neat_prefix = self.neat_prefix_by_predicate_uri.get(space_property_uri)
        warned_spaces: set[str] = set()
        for instance, space in instance_iterable:
            if neat_prefix:
                space = space.removeprefix(neat_prefix)

            clean_space = NamingStandardization.standardize_space_str(space)
            if clean_space != space and space not in warned_spaces:
                self._lookup_issues.append(
                    NeatValueWarning(f"Invalid space in property {space_property}: {space}. Fixed to {clean_space}")
                )
                warned_spaces.add(space)

            self._space_by_instance_uri[instance] = clean_space
