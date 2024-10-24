from dataclasses import dataclass
from typing import Any

from rdflib import Namespace

from cognite.neat._rules.models._base_input import InputComponent, InputRules
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
    UnknownEntity,
    load_value_type,
)
from cognite.neat._rules.models.information._rules_input import InformationInputClass, InformationInputMetadata

from ._rules import AssetClass, AssetMetadata, AssetProperty, AssetRules


@dataclass
class AssetInputMetadata(InformationInputMetadata):
    @classmethod
    def _get_verified_cls(cls) -> type[AssetMetadata]:
        return AssetMetadata


@dataclass
class AssetInputProperty(InputComponent[AssetProperty]):
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
    implementation: str | None = None
    # Only used internally
    inherited: bool = False

    @classmethod
    def _get_verified_cls(cls) -> type[AssetProperty]:
        return AssetProperty

    def dump(self, default_prefix: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["Class"] = ClassEntity.load(self.class_, prefix=default_prefix)
        output["Value Type"] = load_value_type(self.value_type, default_prefix)
        return output


@dataclass
class AssetInputClass(InformationInputClass):
    @classmethod
    def _get_verified_cls(cls) -> type[AssetClass]:
        return AssetClass


@dataclass
class AssetInputRules(InputRules[AssetRules]):
    metadata: AssetInputMetadata
    properties: list[AssetInputProperty]
    classes: list[AssetInputClass]
    prefixes: dict[str, Namespace] | None = None
    last: "AssetInputRules | None" = None
    reference: "AssetInputRules | None" = None

    @classmethod
    def _get_verified_cls(cls) -> type[AssetRules]:
        return AssetRules

    def dump(self) -> dict[str, Any]:
        default_prefix = self.metadata.prefix
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, AssetInputRules):
            reference = self.reference.dump()
        elif isinstance(self.reference, AssetRules):
            # We need to load through the AssetRulesInput to set the correct default space and version
            reference = AssetInputRules.load(self.reference.model_dump()).dump()
        last: dict[str, Any] | None = None
        if isinstance(self.last, AssetInputRules):
            last = self.last.dump()
        elif isinstance(self.last, AssetRules):
            # We need to load through the AssetRulesInput to set the correct default space and version
            last = AssetInputRules.load(self.last.model_dump()).dump()

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_prefix) for prop in self.properties],
            Classes=[class_.dump(default_prefix) for class_ in self.classes],
            Last=last,
            Reference=reference,
        )
