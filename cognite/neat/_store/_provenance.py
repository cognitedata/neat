# we will use prov-o to represent the provenance of the neat graph store
# basically tracking changes that occur in the graph store
# prov-o use concepts of Agent, Activity and Entity to represent provenance
# where in case of neat we have:
# Agent: triples extractors, graph enhancers, contextualizers, etc.
# Activity: write triple, add connection, etc.
# Entity: neat graph store


import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from rdflib import PROV, RDF, Literal, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._shared import FrozenNeatObject, NeatList


@dataclass(frozen=True)
class Agent:
    id_: URIRef = DEFAULT_NAMESPACE.agent
    acted_on_behalf_of: str = "NEAT"

    def as_triples(self):
        return [
            (self.id_, RDF.type, PROV[type(self).__name__]),
            (self.id_, PROV.actedOnBehalfOf, self.acted_on_behalf_of),
        ]


@dataclass(frozen=True)
class Activity:
    was_associated_with: Agent
    ended_at_time: datetime
    started_at_time: datetime
    used: str  # this would be set to for example Extractor, Enhancer, Contextualizer, etc.
    id_: URIRef = DEFAULT_NAMESPACE[f"activity-{uuid.uuid4()}"]

    def as_triples(self):
        return [
            (self.id_, RDF.type, PROV[type(self).__name__]),
            (self.id_, PROV.wasAssociatedWith, self.was_associated_with.id_),
            (self.id_, PROV.startedAtTime, Literal(self.started_at_time)),
            (self.id_, PROV.endedAtTime, Literal(self.ended_at_time)),
            (self.id_, PROV.used, self.used),
        ]


@dataclass(frozen=True)
class Entity:
    was_generated_by: Activity
    was_attributed_to: Agent
    id_: URIRef = DEFAULT_NAMESPACE["graph-store"]

    def as_triples(self):
        return [
            (self.id_, RDF.type, PROV[type(self).__name__]),
            (self.id_, PROV.wasGeneratedBy, self.was_generated_by.id_),
            (self.id_, PROV.wasAttributedTo, self.was_attributed_to.id_),
        ]


@dataclass(frozen=True)
class Change(FrozenNeatObject):
    agent: Agent
    activity: Activity
    entity: Entity
    description: str
    # triples that were added to the graph store
    addition: list[tuple[URIRef, URIRef, URIRef | Literal]] | None = None
    # triples that were removed from the graph store
    subtraction: list[tuple[URIRef, URIRef, URIRef | Literal]] | None = None

    def as_triples(self):
        return self.agent.as_triples() + self.activity.as_triples() + self.entity.as_triples()

    @classmethod
    def record(cls, activity: str, start: datetime, end: datetime, description: str):
        """User friendly method to record a change that occurred in the graph store."""
        agent = Agent()
        activity = Activity(
            used=activity,
            was_associated_with=agent,
            started_at_time=start,
            ended_at_time=end,
        )
        entity = Entity(was_generated_by=activity, was_attributed_to=agent)
        return cls(agent, activity, entity, description)

    def dump(self, aggregate: bool = True) -> dict[str, str]:
        return {
            "Agent": self.agent.id_,
            "Activity": self.activity.id_,
            "Entity": self.entity.id_,
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
