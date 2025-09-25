import itertools
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import yaml
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability, DataModelsAcl
from rdflib import URIRef

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._client._api.data_modeling_loaders import MultiCogniteAPIError
from cognite.neat.v0.core._constants import COGNITE_SPACES
from cognite.neat.v0.core._issues import IssueList, NeatIssue
from cognite.neat.v0.core._issues.errors import ResourceCreationError, ResourceNotFoundError
from cognite.neat.v0.core._issues.warnings import NeatValueWarning
from cognite.neat.v0.core._store import NeatInstanceStore
from cognite.neat.v0.core._utils.collection_ import iterate_progress_bar_if_above_config_threshold
from cognite.neat.v0.core._utils.rdf_ import namespace_as_space, split_uri
from cognite.neat.v0.core._utils.text import NamingStandardization
from cognite.neat.v0.core._utils.upload import UploadResult

from ._base import _END_OF_CLASS, _START_OF_CLASS, CDFLoader


class InstanceSpaceLoader(CDFLoader[dm.SpaceApply]):
    """Loads Instance Space into Cognite Data Fusion (CDF).

    There are three ways to determine the space for each instance:
    1. If `instance_space` is provided, all instances will be assigned to that space, i.e., the space
        is constant for all instances.
    (If not it is set based on the triples (subject, predicate, object) in the graph store.)
    2. If `space_property` is provided, this is the predicate and the space is set to the object. The `instance_space`
       is used as a fallback if the object is not a valid space.
    3. If `use_source_space` is set to True, the instances are assumed to be extracted from CDF and the space is part
        of the subject.

    This class exposes the `space_by_instance_uri` property used by the DMSLoader to lookup space for each instance URI.

    Args:
        graph_store (NeatInstanceStore): The graph store to load the data from.
        instance_space (str): The instance space to load the data into.
        space_property (str): The property to use to determine the space for each instance.
        use_source_space (bool): If True, use the source space of the instances when extracted from CDF.
        neat_prefix_by_predicate_uri (dict[URIRef, str] | None): A dictionary that maps a predicate URIRef to a
            prefix that Neat added to the object upon extraction. This is used to remove the prefix from the
            object before creating the instance.
    """

    def __init__(
        self,
        graph_store: NeatInstanceStore | None = None,
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
        # This is a dictionary mapping instance URIs to their respective spaces
        # This is exposed through the property space_by_instance_uri. If the instance_space or space_property is
        # set (1. and 2.) this is changed to a defaultdict with the instance_space as the default value.
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
        spaces: list[dm.SpaceApply],
        dry_run: bool,
        read_issues: IssueList,
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        cdf_spaces = client.data_modeling.spaces.retrieve([space.space for space in spaces])
        cdf_space_by_id = {item.space: item for item in cdf_spaces}

        to_create = dm.SpaceApplyList([])
        to_update = dm.SpaceApplyList([])
        unchanged = dm.SpaceApplyList([])

        for local_space in spaces:
            cdf_space = cdf_space_by_id.get(local_space.space)
            if cdf_space is None:
                to_create.append(local_space)
            elif cdf_space != local_space.as_write():
                to_update.append(local_space)
            else:
                unchanged.append(local_space)
        loader = client.loaders.spaces
        results: UploadResult[str] = UploadResult("instance spaces")
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
        self._lookup_spaces()
        if self._lookup_issues.has_errors and stop_on_exception:
            raise self._lookup_issues.as_errors()
        yield from self._lookup_issues
        seen: set[str] = set()
        for space_str in set(self.space_by_instance_uri.values()):
            if space_str in seen or space_str in COGNITE_SPACES:
                continue
            yield dm.SpaceApply(space=space_str)
            seen.add(space_str)

    def _lookup_spaces(self) -> None:
        # Case 1: Same instance space for all instances:
        if isinstance(self.instance_space, str) and self.space_property is None and self.use_source_space is False:
            self._space_by_instance_uri = defaultdict(lambda: cast(str, self.instance_space))
            # Adding a dummy entry to ensure that the instance space is included
            self._space_by_instance_uri[URIRef(self.instance_space)] = self.instance_space
            return
        if self.graph_store is None:
            raise ValueError("Graph store must be provided to lookup spaces")
        # Case 3: Use the source space, i.e., the space of the instances when extracted from CDF
        if self.use_source_space and self.instance_space is None and self.space_property is None:
            self._lookup_space_via_instance_uris(self.graph_store)
        # Case 2: Use a property on each instance to determine the space.
        elif self.space_property is not None and self.use_source_space is False:
            if self.instance_space is None:
                raise ValueError(
                    "Missing fallback instance space. This is required when "
                    f"using space_property='{self.space_property}'"
                )
            self._space_by_instance_uri = defaultdict(lambda: cast(str, self.instance_space))
            self._lookup_space_via_property(self.graph_store, self.space_property)
        else:
            raise ValueError("Either 'instance_space', 'space_property', or 'use_source_space' must be provided.")

    def _lookup_space_via_instance_uris(self, graph_store: NeatInstanceStore) -> None:
        instance_iterable = itertools.chain(
            (res[0] for res in graph_store.queries.select.list_instances_ids()),
            graph_store.queries.select.list_instance_object_ids(),
        )

        for instance_uri in instance_iterable:
            namespace, external_id = split_uri(instance_uri)
            space = namespace_as_space(namespace)
            if space is None:
                error = ResourceCreationError(instance_uri, "instance", "This instance was not extracted from CDF.")
                self._lookup_issues.append(error)
            else:
                self._space_by_instance_uri[instance_uri] = space

    def _lookup_space_via_property(self, graph_store: NeatInstanceStore, space_property: str) -> None:
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
