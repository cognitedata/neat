from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

import pandas as pd
from cognite.client import data_modeling as dm
from rdflib import Namespace, URIRef

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model.models._base_unverified import (
    UnverifiedComponent,
    UnverifiedDataModel,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptEntity,
    MultiValueTypeInfo,
    UnknownEntity,
    load_value_type,
)
from cognite.neat.v0.core._utils.rdf_ import uri_display_name

from ._verified import (
    Concept,
    ConceptualDataModel,
    ConceptualMetadata,
    ConceptualProperty,
)


@dataclass
class UnverifiedConceptualMetadata(UnverifiedComponent[ConceptualMetadata]):
    space: str
    external_id: str
    version: str
    creator: str
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None
    physical: str | URIRef | None = None
    source_id: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[ConceptualMetadata]:
        return ConceptualMetadata

    def dump(self, **kwargs: Any) -> dict[str, Any]:
        output = super().dump()
        if self.created is None:
            output["created"] = datetime.now()
        if self.updated is None:
            output["updated"] = datetime.now()
        return output

    def as_data_model_id(self) -> dm.DataModelId:
        return dm.DataModelId(space=self.space, external_id=self.external_id, version=self.version)

    @property
    def prefix(self) -> str:
        return self.space

    @property
    def identifier(self) -> URIRef:
        """Globally unique identifier for the data model.

        !!! note
            Unlike namespace, the identifier does not end with "/" or "#".

        """
        return DEFAULT_NAMESPACE[f"data-model/unverified/conceptual/{self.space}/{self.external_id}/{self.version}"]

    @property
    def namespace(self) -> Namespace:
        """Namespace for the data model used for the entities in the data model."""
        return Namespace(f"{self.identifier}/")


@dataclass
class UnverifiedConceptualProperty(UnverifiedComponent[ConceptualProperty]):
    concept: ConceptEntity | str | UnknownEntity
    property_: str
    value_type: DataType | ConceptEntity | MultiValueTypeInfo | UnknownEntity | str
    name: str | None = None
    description: str | None = None
    min_count: int | None = None
    max_count: int | float | None = None
    default: Any | None = None
    instance_source: str | list[str] | None = None
    # Only used internally
    inherited: bool = False
    neatId: str | URIRef | None = None

    # linking
    physical: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[ConceptualProperty]:
        return ConceptualProperty

    def dump(self, default_prefix: str, **kwargs) -> dict[str, Any]:  # type: ignore
        output = super().dump()
        output["Concept"] = ConceptEntity.load(self.concept, prefix=default_prefix, return_on_failure=True)
        output["Value Type"] = load_value_type(self.value_type, default_prefix, return_on_failure=True)
        return output

    def copy(self, update: dict[str, Any], default_prefix: str) -> "UnverifiedConceptualProperty":
        return cast(
            UnverifiedConceptualProperty,
            type(self)._load({**self.dump(default_prefix), **update}),
        )


@dataclass
class UnverifiedConcept(UnverifiedComponent[Concept]):
    concept: ConceptEntity | str
    name: str | None = None
    description: str | None = None
    implements: str | list[ConceptEntity] | None = None
    instance_source: str | None = None
    neatId: str | URIRef | None = None
    # linking
    physical: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[Concept]:
        return Concept

    @property
    def concept_str(self) -> str:
        return str(self.concept)

    def dump(self, default_prefix: str, **kwargs) -> dict[str, Any]:  # type: ignore
        output = super().dump()
        parent: list[ConceptEntity] | None = None
        if isinstance(self.implements, str):
            self.implements = self.implements.strip()
            parent = [
                ConceptEntity.load(parent_str, prefix=default_prefix, return_on_failure=True)
                for parent_str in self.implements.split(",")
            ]
        elif isinstance(self.implements, list):
            parent = [
                ConceptEntity.load(parent_str, prefix=default_prefix, return_on_failure=True)
                for parent_str in self.implements
            ]
        output["Concept"] = ConceptEntity.load(self.concept, prefix=default_prefix, return_on_failure=True)
        output["Implements"] = parent
        return output


@dataclass
class UnverifiedConceptualDataModel(UnverifiedDataModel[ConceptualDataModel]):
    metadata: UnverifiedConceptualMetadata
    concepts: list[UnverifiedConcept] = field(default_factory=list)
    properties: list[UnverifiedConceptualProperty] = field(default_factory=list)
    prefixes: dict[str, Namespace] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[ConceptualDataModel]:
        return ConceptualDataModel

    def dump(self) -> dict[str, Any]:
        default_prefix = self.metadata.prefix

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_prefix) for prop in self.properties],
            Concepts=[concept.dump(default_prefix) for concept in self.concepts],
            Prefixes=self.prefixes,
        )

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedInformationModel"

    @property
    def display_name(self) -> str:
        return uri_display_name(self.metadata.identifier)

    def _repr_html_(self) -> str:
        summary = {
            "type": "Logical Data Model",
            "intended for": "Information Architect",
            "name": self.metadata.name,
            "external_id": self.metadata.external_id,
            "space": self.metadata.space,
            "version": self.metadata.version,
            "concepts": len(self.concepts),
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
