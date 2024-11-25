from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from rdflib import URIRef

from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, ViewApplyDict
from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import JustRules, ReadRules, VerifiedRules
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.dms._schema import DMSSchema
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._store import NeatGraphStore
from cognite.neat._store._provenance import Change, Provenance
from cognite.neat._utils.cdf.loaders import ViewLoader
from cognite.neat._utils.upload import UploadResultList

from .exceptions import NeatSessionError


class SessionState:
    def __init__(self, store_type: Literal["memory", "oxigraph"]) -> None:
        self.instances = InstancesState(store_type)
        self.data_model = DataModelState()


@dataclass
class InstancesState:
    store_type: Literal["memory", "oxigraph"]
    issue_lists: list[IssueList] = field(default_factory=list)
    outcome: list[UploadResultList] = field(default_factory=list)
    _store: NeatGraphStore | None = field(init=False, default=None)

    @property
    def store(self) -> NeatGraphStore:
        if not self.has_store:
            if self.store_type == "oxigraph":
                self._store = NeatGraphStore.from_oxi_store()
            else:
                self._store = NeatGraphStore.from_memory_store()
        return cast(NeatGraphStore, self._store)

    @property
    def has_store(self) -> bool:
        return self._store is not None

    @property
    def last_outcome(self) -> UploadResultList:
        if not self.outcome:
            raise NeatSessionError(
                "No outcome available. Try using [bold].to.cdf.instances[/bold] to upload a data minstances."
            )
        return self.outcome[-1]


@dataclass
class DataModelState:
    _rules: dict[URIRef, ReadRules | JustRules | VerifiedRules] = field(init=False, default_factory=dict)
    issue_lists: list[IssueList] = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance)
    outcome: list[UploadResultList] = field(default_factory=list)
    _cdf_containers: ContainerApplyDict = field(default_factory=ContainerApplyDict)
    _cdf_views: ViewApplyDict = field(default_factory=ViewApplyDict)

    def write(self, rules: ReadRules | JustRules | VerifiedRules, change: Change) -> None:
        if change.target_entity.id_ in self._rules:
            raise NeatSessionError(f"Data model <{change.target_entity.id_}> already exists.")

        else:
            self._rules[change.target_entity.id_] = rules
            self.provenance.append(change)

    def read(self, id_: URIRef) -> ReadRules | JustRules | VerifiedRules:
        if id_ not in self._rules:
            raise NeatSessionError(f"Data model <{id_}> not found.")
        return self._rules[id_]

    @property
    def unverified_rules(self) -> dict[URIRef, ReadRules]:
        return {id_: rules for id_, rules in self._rules.items() if isinstance(rules, ReadRules)}

    @property
    def verified_rules(self) -> dict[URIRef, VerifiedRules]:
        return {id_: rules for id_, rules in self._rules.items() if isinstance(rules, VerifiedRules)}

    @property
    def last_unverified_rule(self) -> tuple[URIRef, ReadRules]:
        if not self.unverified_rules:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to load a data model.")
        return next(reversed(self.unverified_rules.items()))

    @property
    def last_info_unverified_rule(self) -> tuple[URIRef, ReadRules]:
        if self.unverified_rules:
            for id_, rule in reversed(self.unverified_rules.items()):
                if isinstance(rule.rules, InformationInputRules):
                    return id_, rule

        raise NeatSessionError("No data model available. Try using [bold].read[/bold] to load a data model.")

    @property
    def last_verified_rule(self) -> tuple[URIRef, VerifiedRules]:
        if not self.verified_rules:
            raise NeatSessionError(
                "No data model available to verify. Try using  [bold].read[/bold] to load a data model."
            )
        return next(reversed(self.verified_rules.items()))

    @property
    def last_verified_information_rules(self) -> tuple[URIRef, InformationRules]:
        if self.verified_rules:
            for id_, rules in reversed(self.verified_rules.items()):
                if isinstance(rules, InformationRules):
                    return id_, rules

        raise NeatSessionError(
            "No verified information data model. Try using  [bold].verify()[/bold]"
            " to convert unverified information model to verified information model."
        )

    @property
    def last_verified_dms_rules(self) -> tuple[URIRef, DMSRules]:
        if self.verified_rules:
            for id_, rules in reversed(self.verified_rules.items()):
                if isinstance(rules, DMSRules):
                    return id_, rules

        raise NeatSessionError(
            'No verified DMS data model. Try using  [bold].convert("DMS")[/bold]'
            " to convert verified information model to verified DMS model."
        )

    @property
    def has_unverified_rules(self) -> bool:
        return bool(self.unverified_rules)

    @property
    def has_verified_rules(self) -> bool:
        return bool(self.verified_rules)

    @property
    def last_issues(self) -> IssueList:
        if not self.issue_lists:
            raise NeatSessionError("No issues available. Try using [bold].verify()[/bold] to verify a data model.")
        return self.issue_lists[-1]

    @property
    def last_outcome(self) -> UploadResultList:
        if not self.outcome:
            raise NeatSessionError(
                "No outcome available. Try using [bold].to.cdf.data_model[/bold] to upload a data model."
            )
        return self.outcome[-1]

    def lookup_containers(
        self, client: CogniteClient, container_ids: Sequence[dm.ContainerId]
    ) -> list[dm.ContainerApply]:
        if missing := set(container_ids) - set(self._cdf_containers.keys()):
            cdf_container_ids = list(missing)
            found = client.data_modeling.containers.retrieve(cdf_container_ids).as_write()
            self._cdf_containers.update({container.as_id(): container for container in found})
        return [
            self._cdf_containers[container_id] for container_id in container_ids if container_id in self._cdf_containers
        ]

    def lookup_views(
        self, client: CogniteClient, view_ids: Sequence[dm.ViewId], include_ancestors: bool = True
    ) -> list[dm.ViewApply]:
        if missing := set(view_ids) - set(self._cdf_views.keys()):
            loader = ViewLoader(client)
            cdf_view_ids = list(missing)
            found_read = loader.retrieve(cdf_view_ids)
            if include_ancestors:
                ancestors = loader.retrieve_all_ancestors(cdf_view_ids, include_connections=True)
                found_read.extend(ancestors)

            found = [loader.as_write(read_view) for read_view in found_read]
            self._cdf_views.update({view.as_id(): view for view in found})
        output = [self._cdf_views[view_id] for view_id in view_ids if view_id in self._cdf_views]
        if not include_ancestors:
            return output

        to_check = output.copy()
        seen = set(view_ids)
        while to_check:
            checking = to_check.pop()
            connected_views = ViewLoader.get_connected_views(checking, seen, include_connections=True)
            for connected_id in connected_views:
                if connected_id in self._cdf_views:
                    found_view = self._cdf_views[connected_id]
                    output.append(found_view)
                    to_check.append(found_view)
                seen.add(connected_id)
        return output

    def lookup_schema(
        self,
        client: CogniteClient,
        views: list[dm.ViewId],
        containers: list[dm.ContainerId],
        include_ancestors: bool = True,
    ) -> DMSSchema:
        views = ViewApplyDict(self.lookup_views(client, views, include_ancestors=include_ancestors))

        container_set = set(containers) | {
            container for view in views.values() for container in view.referenced_containers()
        }

        return DMSSchema(
            data_model=dm.DataModelApply(
                space="NEAT_LOOKUP",
                external_id="NEAT_LOOKUP",
                version="NEAT_LOOKUP",
                views=list(views.keys()),
            ),
            views=views,
            containers=ContainerApplyDict(self.lookup_containers(client, list(container_set))),
        )
