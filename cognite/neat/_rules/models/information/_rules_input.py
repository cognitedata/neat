from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from cognite.client import data_modeling as dm
from rdflib import Namespace, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._rules.models._base_input import InputComponent, InputRules
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
    UnknownEntity,
    load_value_type,
)
from cognite.neat._utils.rdf_ import uri_display_name

from ._rules import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
    InformationRules,
)


@dataclass
class InformationInputMetadata(InputComponent[InformationMetadata]):
    space: str
    external_id: str
    version: str
    creator: str
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None
    physical: str | URIRef | None = None
    conceptual: str | URIRef | None = None
    source_id: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[InformationMetadata]:
        return InformationMetadata

    def dump(self, **kwargs) -> dict[str, Any]:
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
        return DEFAULT_NAMESPACE[f"data-model/unverified/logical/{self.space}/{self.external_id}/{self.version}"]

    @property
    def namespace(self) -> Namespace:
        """Namespace for the data model used for the entities in the data model."""
        return Namespace(f"{self.identifier}/")


@dataclass
class InformationInputProperty(InputComponent[InformationProperty]):
    class_: ClassEntity | str
    property_: str
    value_type: DataType | ClassEntity | MultiValueTypeInfo | UnknownEntity | str
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
    conceptual: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[InformationProperty]:
        return InformationProperty

    def dump(self, default_prefix: str, **kwargs) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["Class"] = ClassEntity.load(self.class_, prefix=default_prefix)
        output["Value Type"] = load_value_type(self.value_type, default_prefix)
        return output


@dataclass
class InformationInputClass(InputComponent[InformationClass]):
    class_: ClassEntity | str
    name: str | None = None
    description: str | None = None
    implements: str | list[ClassEntity] | None = None
    instance_source: str | None = None
    neatId: str | URIRef | None = None
    # linking
    physical: str | URIRef | None = None
    conceptual: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[InformationClass]:
        return InformationClass

    @property
    def class_str(self) -> str:
        return str(self.class_)

    def dump(self, default_prefix: str, **kwargs) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        parent: list[ClassEntity] | None = None
        if isinstance(self.implements, str):
            self.implements = self.implements.strip()
            parent = [ClassEntity.load(parent, prefix=default_prefix) for parent in self.implements.split(",")]
        elif isinstance(self.implements, list):
            parent = [ClassEntity.load(parent_, prefix=default_prefix) for parent_ in self.implements]
        output["Class"] = ClassEntity.load(self.class_, prefix=default_prefix)
        output["Implements"] = parent
        return output


@dataclass
class InformationInputRules(InputRules[InformationRules]):
    metadata: InformationInputMetadata
    properties: list[InformationInputProperty] = field(default_factory=list)
    classes: list[InformationInputClass] = field(default_factory=list)
    prefixes: dict[str, Namespace] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[InformationRules]:
        return InformationRules

    def dump(self) -> dict[str, Any]:
        default_prefix = self.metadata.prefix

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_prefix) for prop in self.properties],
            Classes=[class_.dump(default_prefix) for class_ in self.classes],
            Prefixes=self.prefixes,
        )

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedInformationModel"

    @property
    def display_name(self):
        return uri_display_name(self.metadata.identifier)

    def _repr_html_(self) -> str:
        summary = {
            "type": "Logical Data Model",
            "intended for": "Information Architect",
            "name": self.metadata.name,
            "external_id": self.metadata.external_id,
            "space": self.metadata.space,
            "version": self.metadata.version,
            "classes": len(self.classes),
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
