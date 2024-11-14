from dataclasses import dataclass, field
from typing import Literal, cast

from rdflib import URIRef

from cognite.neat._issues import IssueList
from cognite.neat._rules._shared import JustRules, ReadRules, VerifiedRules
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._store import NeatGraphStore
from cognite.neat._store._provenance import Change, Provenance
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
