"""
We use prov-o to represent the provenance of instances and data models
basically tracking changes that occur.
prov-o use concepts of Agent, Activity and Entity to represent provenance
where in case of neat when dealing with instances we have:

 * Agent: triples extractors, graph enhancers, contextualizers, etc.
 * Activity: write/remove triples such as add connection, etc.
 * Entity: neat graph store

 and in case of data models we have:

 * Agent: Rules importers, exporters, transformers, etc.
 * Activity: convert, verify, etc.
 * Entity: data model (aka Rules)

"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TypeVar

from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
from rdflib import PROV, RDF, Literal, URIRef

from cognite.neat._constants import CDF_NAMESPACE, DEFAULT_NAMESPACE
from cognite.neat._rules._shared import JustRules, ReadRules, VerifiedRules
from cognite.neat._shared import FrozenNeatObject, NeatList, Triple


@dataclass(frozen=True)
class Agent:
    id_: URIRef = DEFAULT_NAMESPACE.agent
    acted_on_behalf_of: str = "NEAT"

    def as_triples(self) -> list[Triple]:
        return [
            (self.id_, RDF.type, PROV[type(self).__name__]),
            (self.id_, PROV.actedOnBehalfOf, Literal(self.acted_on_behalf_of)),
        ]


CDF_AGENT = Agent(acted_on_behalf_of="UNKNOWN", id_=CDF_NAMESPACE["agent"])
NEAT_AGENT = Agent(acted_on_behalf_of="UNKNOWN", id_=DEFAULT_NAMESPACE["agent"])
UNKNOWN_AGENT = Agent(acted_on_behalf_of="UNKNOWN", id_=DEFAULT_NAMESPACE["unknown-agent"])


@dataclass(frozen=True)
class Entity:
    was_attributed_to: Agent
    was_generated_by: Optional["Activity"] = field(default=None, repr=False)
    id_: URIRef = DEFAULT_NAMESPACE["graph-store"]

    def as_triples(self) -> list[Triple]:
        output: list[tuple[URIRef, URIRef, Literal | URIRef]] = [
            (self.id_, RDF.type, PROV[type(self).__name__]),
            (self.id_, PROV.wasAttributedTo, self.was_attributed_to.id_),
        ]

        if self.was_generated_by:
            output.append(
                (
                    self.id_,
                    PROV.wasGeneratedBy,
                    self.was_generated_by.id_,
                )
            )

        return output

    @classmethod
    def from_data_model_id(cls, data_model_id: DataModelIdentifier) -> "Entity":
        data_model_id = DataModelId.load(data_model_id)

        return cls(
            was_attributed_to=CDF_AGENT,
            id_=CDF_NAMESPACE[
                f"dms/data-model/{data_model_id.space}/{data_model_id.external_id}/{data_model_id.version}"
            ],
        )

    @classmethod
    def from_rules(
        cls,
        rules: ReadRules | JustRules | VerifiedRules,
        agent: Agent | None = None,
        activity: "Activity | None" = None,
    ) -> "Entity":
        agent = agent or UNKNOWN_AGENT
        if isinstance(rules, VerifiedRules):
            return cls(
                was_attributed_to=agent,
                was_generated_by=activity,
                id_=rules.metadata.identifier,
            )

        elif isinstance(rules, ReadRules | JustRules) and rules.rules is not None:
            return cls(
                was_attributed_to=agent,
                was_generated_by=activity,
                id_=rules.rules.metadata.identifier,
            )
        else:
            return cls(
                was_attributed_to=agent,
                was_generated_by=activity,
                id_=DEFAULT_NAMESPACE["unknown-entity"],
            )

    @classmethod
    def new_unknown_entity(cls) -> "Entity":
        return cls(
            was_attributed_to=UNKNOWN_AGENT,
            id_=DEFAULT_NAMESPACE[f"unknown-entity/{uuid.uuid4()}"],
        )


INSTANCES_ENTITY = Entity(was_attributed_to=NEAT_AGENT, id_=CDF_NAMESPACE["instances"])


@dataclass(frozen=True)
class Activity:
    was_associated_with: Agent
    ended_at_time: datetime
    started_at_time: datetime
    used: str | Entity | None = None
    id_: URIRef = field(default_factory=lambda: DEFAULT_NAMESPACE[f"activity-{uuid.uuid4()}"])

    def as_triples(self) -> list[Triple]:
        output: list[tuple[URIRef, URIRef, Literal | URIRef]] = [
            (self.id_, RDF.type, PROV[type(self).__name__]),
            (self.id_, PROV.wasAssociatedWith, self.was_associated_with.id_),
            (self.id_, PROV.startedAtTime, Literal(self.started_at_time)),
            (self.id_, PROV.endedAtTime, Literal(self.ended_at_time)),
        ]

        if self.used:
            output.append(
                (
                    self.id_,
                    PROV.used,
                    (self.used.id_ if isinstance(self.used, Entity) else Literal(self.used)),
                )
            )

        return output


@dataclass(frozen=True)
class Change(FrozenNeatObject):
    agent: Agent
    activity: Activity
    target_entity: Entity
    description: str
    source_entity: Entity = field(default_factory=Entity.new_unknown_entity)

    def as_triples(self) -> list[Triple]:
        return (
            self.source_entity.as_triples()
            + self.agent.as_triples()
            + self.activity.as_triples()
            + self.target_entity.as_triples()  # type: ignore[operator]
        )

    @classmethod
    def record(cls, activity: str, start: datetime, end: datetime, description: str) -> "Change":
        """User friendly method to record a change that occurred in the graph store."""
        agent = Agent()
        activity = Activity(
            used=activity,
            was_associated_with=agent,
            started_at_time=start,
            ended_at_time=end,
        )
        target_entity = Entity(was_generated_by=activity, was_attributed_to=agent)
        return cls(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=description,
        )

    @classmethod
    def from_rules_activity(
        cls,
        rules: ReadRules | JustRules | VerifiedRules,
        agent: Agent,
        start: datetime,
        end: datetime,
        description: str,
        source_entity: Entity | None = None,
    ) -> "Change":
        source_entity = source_entity or Entity.new_unknown_entity()
        activity = Activity(
            started_at_time=start,
            ended_at_time=end,
            was_associated_with=agent,
            used=source_entity,
        )

        target_entity = Entity.from_rules(rules, agent, activity)

        return cls(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=description,
            source_entity=source_entity,
        )

    def dump(self, aggregate: bool = True) -> dict[str, str]:
        return {
            "Source Entity": self.source_entity.id_,
            "Agent": self.agent.id_,
            "Activity": self.activity.id_,
            "Target Entity": self.target_entity.id_,
            "Description": self.description,
        }


T_Change = TypeVar("T_Change", bound=Change)


class Provenance(NeatList[Change]):
    def __init__(self, changes: Sequence[T_Change] | None = None):
        super().__init__(changes or [])

    def activity_took_place(self, activity: str) -> bool:
        return any(change.activity.used == activity for change in self)

    def __delitem__(self, *args, **kwargs):
        raise TypeError("Cannot delete change from provenance")

    def __setitem__(self, *args, **kwargs):
        raise TypeError("Cannot modify change from provenance")

    def _repr_html_(self) -> str:
        text = "<br /><strong>Provenance</strong>:<ul>"

        for change in self:
            text += f"<li>{change.description}</li>"

        text += "</ul>"

        return text

    def activity(self, id_: URIRef) -> Activity | None:
        return next((change.activity for change in self if change.activity.id_ == id_), None)

    def agent(self, id_: URIRef) -> Agent | None:
        return next((change.agent for change in self if change.agent.id_ == id_), None)

    def target_entity(self, id_: URIRef) -> Entity | None:
        return next(
            (change.target_entity for change in self if change.target_entity.id_ == id_),
            None,
        )

    def source_entity(self, id_: URIRef) -> Entity | None:
        return next(
            (change.source_entity for change in self if change.source_entity.id_ == id_),
            None,
        )

    def as_triples(self) -> Iterable[Triple]:
        for change in self:
            yield from change.as_triples()
