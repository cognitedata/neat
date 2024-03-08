import json
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, overload

from pydantic import ValidationError

from cognite.neat.rules import validation
from cognite.neat.rules._shared import Rules
from cognite.neat.rules.importers._base import BaseImporter
from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules._types import (
    XSD_VALUE_TYPE_MAPPINGS,
    ClassEntity,
    ParentClassEntity,
    XSDValueType,
)
from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty
from cognite.neat.rules.validation import IssueList

from ._v3_spec import DTDL_CLS_BY_TYPE, DTMI, DTDLBase, Enum, Interface, Object, Property, Relationship, Schema


class DTDLImporter(BaseImporter):
    """Importer for DTDL (Digital Twin Definition Language) files. It can import a directory containing DTDL files and
    convert them to InformationRules.

    The DTDL v3 standard is supported and defined at
    https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v3/DTDL.v3.md

    """

    def __init__(self, items: Sequence[DTDLBase], title: str | None = None) -> None:
        self._items = items
        self.title = title

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        for filepath in directory.glob("**/*.json"):
            raw = json.loads(filepath.read_text())
            if isinstance(raw, dict):
                raw_list = [raw]
            elif isinstance(raw, list):
                raw_list = raw
            else:
                raise ValueError(f"Invalid json file {filepath}")
            for item in raw_list:
                if not (type_ := item.get("@type")):
                    warnings.warn(f"Invalid json file {filepath}. Missing '@type' key.", stacklevel=2)
                    continue
                cls_ = DTDL_CLS_BY_TYPE.get(type_)
                if cls_ is None:
                    warnings.warn(f"Invalid json file {filepath}. Unknown '@type' {type_}", stacklevel=2)
                    continue
                items.append(cls_.model_validate(item))
        return cls(items, directory.name)

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        container = _DTDLConverter()

        container.convert(self._items)

        try:
            rules = InformationRules(
                metadata=self._default_metadata(),
                properties=SheetList[InformationProperty](data=container.properties),
                classes=SheetList[InformationClass](data=container.classes),
            )
        except ValidationError as e:
            container.issues.extend(validation.Error.from_pydantic_errors(e.errors()))
            if errors == "continue":
                return None, container.issues
            else:
                raise container.issues.as_errors() from e

        return self._to_output(rules, container.issues, errors, role)


class _DTDLConverter:
    def __init__(self) -> None:
        self.issues: IssueList = IssueList([])
        self.properties: list[InformationProperty] = []
        self.classes: list[InformationClass] = []
        self._item_by_id: dict[DTMI, DTDLBase] = {}

        self._method_by_type: dict[type[DTDLBase], Callable[[DTDLBase, str | None], None]] = {
            Interface: self.convert_interface,  # type: ignore[dict-item]
            Property: self.convert_property,  # type: ignore[dict-item]
            Relationship: self.convert_relationship,  # type: ignore[dict-item]
            Object: self.convert_object,  # type: ignore[dict-item]
        }

    def convert(self, items: Sequence[DTDLBase]) -> None:
        self._item_by_id.update({item.id_: item for item in items if item.id_ is not None})
        # Update schema objects which are reusable
        self._item_by_id.update(
            {
                schema.id_: schema
                for item in items
                if isinstance(item, Interface)
                for schema in item.schemas or []
                if isinstance(schema.id_, DTMI) and isinstance(schema, DTDLBase)
            }
        )

        for item in items:
            self.convert_item(item)

    def convert_item(self, item: DTDLBase, parent: str | None = None) -> None:
        convert_method = self._method_by_type.get(type(item))
        if convert_method is not None:
            convert_method(item, parent)
        else:
            self.issues.append(
                validation.UnknownComponent(
                    component_type=item.type,
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )

    def convert_interface(self, item: Interface, _: str | None) -> None:
        class_ = InformationClass(
            class_=item.id_.as_class_id(),
            name=item.display_name,
            description=item.description,
            comment=item.comment,
            parent=[ParentClassEntity.from_raw(parent.as_class_id()) for parent in item.extends or []] or None,
        )
        self.classes.append(class_)
        for sub_item_or_id in item.contents or []:
            if isinstance(sub_item_or_id, DTMI) and sub_item_or_id not in self._item_by_id:
                self.issues.append(
                    validation.UnknownProperty(
                        component_type=item.type,
                        property_name=sub_item_or_id.as_class_id(),
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump(),
                    )
                )
            elif isinstance(sub_item_or_id, DTMI):
                sub_item = self._item_by_id[sub_item_or_id]
                self.convert_item(sub_item, class_.class_)
            else:
                self.convert_item(sub_item_or_id, class_.class_)
        # interface.schema objects are handled in the convert method

    def convert_property(
        self, item: Property, parent: str | None, min_count: int | None = 0, max_count: int | None = 1
    ) -> None:
        if parent is None:
            self.issues.append(
                validation.MissingParentDefinition(
                    component_type=item.type,
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
        value_type = self.schema_to_value_type(item.schema_, item)
        if value_type is None:
            return None

        prop = InformationProperty(
            class_=parent,
            property_=item.name,
            name=item.display_name,
            description=item.description,
            comment=item.comment,
            value_type=value_type,
            min_count=min_count,
            max_count=max_count,
        )
        self.properties.append(prop)

    def convert_relationship(self, item: Relationship, parent: str | None) -> None:
        if parent is None:
            self.issues.append(
                validation.MissingParentDefinition(
                    component_type=item.type,
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
        if item.target is not None:
            prop = InformationProperty(
                class_=parent,
                property_=item.name,
                name=item.display_name,
                description=item.description,
                min_count=item.min_multiplicity,
                max_count=item.max_multiplicity,
                comment=item.comment,
                value_type=ClassEntity.from_raw(item.target.as_class_id()),
            )
            self.properties.append(prop)
        elif item.properties is not None:
            for prop_ in item.properties or []:
                self.convert_property(prop_, parent, item.min_multiplicity, item.max_multiplicity)

    def convert_object(self, item: Object, _: str | None) -> None:
        if item.id_ is None:
            self.issues.append(
                validation.MissingIdentifier(
                    component_type=item.type,
                    instance_name=item.display_name,
                )
            )
            return None

        class_ = InformationClass(
            class_=item.id_.as_class_id(),
            name=item.display_name,
            description=item.description,
            comment=item.comment,
        )
        self.classes.append(class_)

        for field_ in item.fields or []:
            value_type = self.schema_to_value_type(field_.schema_, item)
            if value_type is None:
                continue
            prop = InformationProperty(
                class_=class_.class_,
                name=field_.name,
                description=field_.description,
                property_=field_.name,
                value_type=value_type,
                min_count=0,
                max_count=1,
            )
            self.properties.append(prop)

    def schema_to_value_type(self, schema: Schema | DTMI | None, item: DTDLBase) -> XSDValueType | ClassEntity | None:
        input_type = self._item_by_id.get(schema) if isinstance(schema, DTMI) else schema

        if isinstance(input_type, Enum):
            return XSD_VALUE_TYPE_MAPPINGS["string"]
        elif isinstance(input_type, str) and input_type in XSD_VALUE_TYPE_MAPPINGS:
            return XSD_VALUE_TYPE_MAPPINGS[input_type]
        elif isinstance(input_type, str):
            self.issues.append(
                validation.UnsupportedPropertyType(
                    component_type=item.type,
                    property_type=input_type,
                    property_name="schema",
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
        elif isinstance(input_type, Object):
            if input_type.id_ is None:
                self.issues.append(
                    validation.MissingIdentifier(
                        component_type=input_type.type,
                        instance_name=input_type.display_name,
                    )
                )
                return XSD_VALUE_TYPE_MAPPINGS["json"]
            else:
                self.convert_object(input_type, None)
                return ClassEntity.from_raw(input_type.id_.as_class_id())
        else:
            self.issues.append(
                validation.UnknownProperty(
                    component_type=item.type,
                    property_name="schema",
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
