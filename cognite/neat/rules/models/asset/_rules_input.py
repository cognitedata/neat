from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast, overload

from cognite.neat.rules.models._base import _add_alias
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
    Unknown,
    UnknownEntity,
)
from cognite.neat.rules.models.information._rules_input import InformationClassInput, InformationMetadataInput

from ._rules import AssetProperty, AssetRules


@dataclass
class AssetMetadataInput(InformationMetadataInput): ...


@dataclass
class AssetPropertyInput:
    class_: str
    property_: str
    value_type: str
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

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "AssetPropertyInput": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["AssetPropertyInput"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "AssetPropertyInput | list[AssetPropertyInput] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(list[dict[str, Any]], data.get("data") if isinstance(data, dict) else data)
            return [loaded for item in items if (loaded := cls.load(item)) is not None]

        _add_alias(data, AssetProperty)
        return cls(
            class_=data.get("class_"),  # type: ignore[arg-type]
            property_=data.get("property_"),  # type: ignore[arg-type]
            name=data.get("name", None),
            description=data.get("description", None),
            comment=data.get("comment", None),
            value_type=data.get("value_type"),  # type: ignore[arg-type]
            min_count=data.get("min_count", None),
            max_count=data.get("max_count", None),
            default=data.get("default", None),
            reference=data.get("reference", None),
            match_type=data.get("match_type", None),
            transformation=data.get("transformation", None),
            implementation=data.get("implementation", None),
        )

    def dump(self, default_prefix: str) -> dict[str, Any]:
        value_type: MultiValueTypeInfo | DataType | ClassEntity | UnknownEntity

        # property holding xsd data type
        # check if it is multi value type
        if "|" in self.value_type:
            value_type = MultiValueTypeInfo.load(self.value_type)
            value_type.set_default_prefix(default_prefix)

        elif DataType.is_data_type(self.value_type):
            value_type = DataType.load(self.value_type)

        # unknown value type
        elif self.value_type == str(Unknown):
            value_type = UnknownEntity()

        # property holding link to class
        else:
            value_type = ClassEntity.load(self.value_type, prefix=default_prefix)

        return {
            "Class": ClassEntity.load(self.class_, prefix=default_prefix),
            "Property": self.property_,
            "Name": self.name,
            "Description": self.description,
            "Comment": self.comment,
            "Value Type": value_type,
            "Min Count": self.min_count,
            "Max Count": self.max_count,
            "Default": self.default,
            "Reference": self.reference,
            "Match Type": self.match_type,
            "Transformation": self.transformation,
            "Implementation": self.implementation,
        }


class AssetClassInput(InformationClassInput): ...


@dataclass
class AssetRulesInput:
    metadata: AssetMetadataInput
    properties: Sequence[AssetPropertyInput]
    classes: Sequence[AssetClassInput]
    last: "AssetRulesInput | AssetRules | None" = None
    reference: "AssetRulesInput | AssetRules | None" = None

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "AssetRulesInput": ...

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    def load(cls, data: dict | None) -> "AssetRulesInput | None":
        if data is None:
            return None
        _add_alias(data, AssetRules)

        return cls(
            metadata=AssetMetadataInput.load(data.get("metadata")),  # type: ignore[arg-type]
            properties=AssetPropertyInput.load(data.get("properties")),  # type: ignore[arg-type]
            classes=InformationClassInput.load(data.get("classes")),  # type: ignore[arg-type]
            last=AssetRulesInput.load(data.get("last")),
            reference=AssetRulesInput.load(data.get("reference")),
        )

    def as_rules(self) -> AssetRules:
        return AssetRules.model_validate(self.dump())

    def dump(self) -> dict[str, Any]:
        default_prefix = self.metadata.prefix
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, AssetRulesInput):
            reference = self.reference.dump()
        elif isinstance(self.reference, AssetRules):
            # We need to load through the AssetRulesInput to set the correct default space and version
            reference = AssetRulesInput.load(self.reference.model_dump()).dump()
        last: dict[str, Any] | None = None
        if isinstance(self.last, AssetRulesInput):
            last = self.last.dump()
        elif isinstance(self.last, AssetRules):
            # We need to load through the AssetRulesInput to set the correct default space and version
            last = AssetRulesInput.load(self.last.model_dump()).dump()

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_prefix) for prop in self.properties],
            Classes=[class_.dump(default_prefix) for class_ in self.classes],
            Last=last,
            Reference=reference,
        )
