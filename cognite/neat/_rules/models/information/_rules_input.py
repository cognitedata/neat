from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from rdflib import Namespace

from cognite.neat._rules.models._base_input import InputComponent, InputRules
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
    UnknownEntity,
    load_value_type,
)

from ._rules import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
    InformationRules,
)


@dataclass
class InformationInputMetadata(InputComponent[InformationMetadata]):
    schema_: Literal["complete", "partial", "extended"]
    prefix: str
    namespace: str
    version: str
    creator: str
    data_model_type: Literal["solution", "enterprise"] = "enterprise"
    extension: Literal["addition", "reshape", "rebuild"] = "addition"
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None
    license: str | None = None
    rights: str | None = None

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


@dataclass
class InformationInputProperty(InputComponent[InformationProperty]):
    class_: ClassEntity | str
    property_: str
    value_type: DataType | ClassEntity | MultiValueTypeInfo | UnknownEntity | str
    name: str | None = None
    description: str | None = None
    comment: str | None = None
    min_count: int | None = None
    max_count: int | float | None = None
    default: Any | None = None
    reference: str | None = None
    match_type: str | None = None
    transformation: str | None = None
    # Only used internally
    inherited: bool = False

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
    comment: str | None = None
    parent: str | list[ClassEntity] | None = None
    reference: str | None = None
    match_type: str | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[InformationClass]:
        return InformationClass

    @property
    def class_str(self) -> str:
        return str(self.class_)

    def dump(self, default_prefix: str, **kwargs) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        parent: list[ClassEntity] | None = None
        if isinstance(self.parent, str):
            parent = [ClassEntity.load(parent, prefix=default_prefix) for parent in self.parent.split(",")]
        elif isinstance(self.parent, list):
            parent = [ClassEntity.load(parent_, prefix=default_prefix) for parent_ in self.parent]
        output["Class"] = ClassEntity.load(self.class_, prefix=default_prefix)
        output["Parent Class"] = parent
        return output


@dataclass
class InformationInputRules(InputRules[InformationRules]):
    metadata: InformationInputMetadata
    properties: list[InformationInputProperty] = field(default_factory=list)
    classes: list[InformationInputClass] = field(default_factory=list)
    prefixes: dict[str, Namespace] | None = None
    last: "InformationInputRules | None" = None
    reference: "InformationInputRules | None" = None

    @classmethod
    def _get_verified_cls(cls) -> type[InformationRules]:
        return InformationRules

    def dump(self) -> dict[str, Any]:
        default_prefix = self.metadata.prefix
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, InformationInputRules):
            reference = self.reference.dump()
        elif isinstance(self.reference, InformationRules):
            # We need to load through the InformationRulesInput to set the correct default space and version
            reference = InformationInputRules.load(self.reference.model_dump()).dump()
        last: dict[str, Any] | None = None
        if isinstance(self.last, InformationInputRules):
            last = self.last.dump()
        elif isinstance(self.last, InformationRules):
            # We need to load through the InformationRulesInput to set the correct default space and version
            last = InformationInputRules.load(self.last.model_dump()).dump()

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_prefix) for prop in self.properties],
            Classes=[class_.dump(default_prefix) for class_ in self.classes],
            Prefixes=self.prefixes,
            Last=last,
            Reference=reference,
        )

    def _repr_html_(self) -> str:
        summary = {
            "type": "Logical Data Model",
            "intended for": "Information Architect",
            "name": self.metadata.name,
            "external_id": self.metadata.prefix,
            "version": self.metadata.version,
            "classes": len(self.classes),
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore
