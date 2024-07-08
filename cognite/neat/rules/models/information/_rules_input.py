from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast, overload

from rdflib import Namespace

from cognite.neat.rules.models._base import (
    DataModelType,
    ExtensionCategory,
    SchemaCompleteness,
    _add_alias,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
    ParentClassEntity,
    Unknown,
    UnknownEntity,
)

from ._rules import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
    InformationRules,
)


@dataclass
class InformationMetadataInput:
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
    def load(cls, data: dict[str, Any] | None) -> "InformationMetadataInput | None":
        if data is None:
            return None
        _add_alias(data, InformationMetadata)
        return cls(
            data_model_type=data.get("data_model_type", "enterprise"),
            extension=data.get("extension", "addition"),
            schema_=data.get("schema_", "partial"),  # type: ignore[arg-type]
            version=data.get("version"),  # type: ignore[arg-type]
            namespace=data.get("namespace"),  # type: ignore[arg-type]
            prefix=data.get("prefix"),  # type: ignore[arg-type]
            name=data.get("name"),
            creator=data.get("creator"),  # type: ignore[arg-type]
            description=data.get("description"),
            created=data.get("created"),
            updated=data.get("updated"),
            license=data.get("license"),
            rights=data.get("rights"),
        )

    def dump(self) -> dict[str, Any]:
        return dict(
            dataModelType=DataModelType(self.data_model_type),
            schema=SchemaCompleteness(self.schema_),
            extension=ExtensionCategory(self.extension),
            namespace=Namespace(self.namespace),
            prefix=self.prefix,
            version=self.version,
            name=self.name,
            creator=self.creator,
            description=self.description,
            created=self.created or datetime.now(),
            updated=self.updated or datetime.now(),
        )


@dataclass
class InformationPropertyInput:
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

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "InformationPropertyInput": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["InformationPropertyInput"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "InformationPropertyInput | list[InformationPropertyInput] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(
                list[dict[str, Any]],
                data.get("data") if isinstance(data, dict) else data,
            )
            return [loaded for item in items if (loaded := cls.load(item)) is not None]

        _add_alias(data, InformationProperty)
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
        }


@dataclass
class InformationClassInput:
    class_: str
    name: str | None = None
    description: str | None = None
    comment: str | None = None
    parent: str | None = None
    reference: str | None = None
    match_type: str | None = None

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "InformationClassInput": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["InformationClassInput"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "InformationClassInput | list[InformationClassInput] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(
                list[dict[str, Any]],
                data.get("data") if isinstance(data, dict) else data,
            )
            return [loaded for item in items if (loaded := cls.load(item)) is not None]
        _add_alias(data, InformationClass)
        return cls(
            class_=data.get("class_"),  # type: ignore[arg-type]
            name=data.get("name", None),
            description=data.get("description", None),
            comment=data.get("comment", None),
            parent=data.get("parent", None),
            reference=data.get("reference", None),
            match_type=data.get("match_type", None),
        )

    def dump(self, default_prefix: str) -> dict[str, Any]:
        return {
            "Class": ClassEntity.load(self.class_, prefix=default_prefix),
            "Name": self.name,
            "Description": self.description,
            "Comment": self.comment,
            "Reference": self.reference,
            "Match Type": self.match_type,
            "Parent Class": (
                [ParentClassEntity.load(parent, prefix=default_prefix) for parent in self.parent.split(",")]
                if self.parent
                else None
            ),
        }


@dataclass
class InformationRulesInput:
    metadata: InformationMetadataInput
    properties: Sequence[InformationPropertyInput]
    classes: Sequence[InformationClassInput]
    prefixes: "dict[str, Namespace] | None" = None
    last: "InformationRulesInput | InformationRules | None" = None
    reference: "InformationRulesInput | InformationRules | None" = None

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "InformationRulesInput": ...

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    def load(cls, data: dict | None) -> "InformationRulesInput | None":
        if data is None:
            return None
        _add_alias(data, InformationRules)

        return cls(
            metadata=InformationMetadataInput.load(data.get("metadata")),  # type: ignore[arg-type]
            properties=InformationPropertyInput.load(data.get("properties")),  # type: ignore[arg-type]
            classes=InformationClassInput.load(data.get("classes")),  # type: ignore[arg-type]
            prefixes=data.get("prefixes"),
            last=InformationRulesInput.load(data.get("last")),
            reference=InformationRulesInput.load(data.get("reference")),
        )

    def as_rules(self) -> InformationRules:
        return InformationRules.model_validate(self.dump())

    def dump(self) -> dict[str, Any]:
        default_prefix = self.metadata.prefix
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, InformationRulesInput):
            reference = self.reference.dump()
        elif isinstance(self.reference, InformationRules):
            # We need to load through the InformationRulesInput to set the correct default space and version
            reference = InformationRulesInput.load(self.reference.model_dump()).dump()
        last: dict[str, Any] | None = None
        if isinstance(self.last, InformationRulesInput):
            last = self.last.dump()
        elif isinstance(self.last, InformationRules):
            # We need to load through the InformationRulesInput to set the correct default space and version
            last = InformationRulesInput.load(self.last.model_dump()).dump()

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_prefix) for prop in self.properties],
            Classes=[class_.dump(default_prefix) for class_ in self.classes],
            Prefixes=self.prefixes,
            Last=last,
            Reference=reference,
        )
