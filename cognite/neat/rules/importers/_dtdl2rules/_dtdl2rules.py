import json
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal, overload

from cognite.neat.rules import validation
from cognite.neat.rules._shared import Rules
from cognite.neat.rules.importers._base import BaseImporter
from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules._types import (
    XSD_VALUE_TYPE_MAPPINGS,
    ClassEntity,
    ParentClassEntity,
)
from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty
from cognite.neat.rules.validation import IssueList

from ._v3_spec import DTDL_CLS_BY_TYPE, DTMI, DTDLBase, Enum, Interface, Property, Relationship


class DTDLImporter(BaseImporter):
    """Importer for DTDL (Digital Twin Definition Language) files. It can import a directory containing DTDL files and
    convert them to InformationRules.

    The DTDL v3 standard is supported and defined at
    https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v3/DTDL.v3.md

    """

    def __init__(self, items: Sequence[DTDLBase], title: str | None = None):
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

        rules = InformationRules(
            metadata=self._default_metadata(),
            properties=SheetList[InformationProperty](data=container.properties),
            classes=SheetList[InformationClass](data=container.classes),
        )

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
        }

    def convert(self, items: Sequence[DTDLBase]) -> None:
        self._item_by_id.update({item.id_: item for item in items if item.id_ is not None})

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
            parent=[ParentClassEntity.from_raw(parent.as_class_id()) for parent in item.extends or []],
        )
        self.classes.append(class_)
        for subitem in item.contents or []:
            subitem_ = self._item_by_id.get(subitem) if isinstance(subitem, DTMI) else subitem
            if subitem_ is None:
                self.issues.append(
                    validation.UnknownProperty(
                        component_type=item.type if isinstance(item, DTDLBase) else item,
                        property_name=subitem.type if isinstance(subitem, DTDLBase) else str(subitem),
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump() if item.id_ else None,
                    )
                )
                continue
            self.convert_item(subitem_, class_.class_)
        for subitem in item.schemas or []:
            self.issues.append(
                validation.UnknownProperty(
                    component_type=item.type,
                    property_name=subitem.type,
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )

    def convert_property(self, item: Property, parent: str | None) -> None:
        if parent is None:
            self.issues.append(
                validation.MissingParentDefinition(
                    component_type=item.type,
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
        input_type = self._item_by_id.get(item.schema_) if isinstance(item.schema_, DTMI) else item.schema_
        if isinstance(input_type, Enum):
            value_type = "string"
        elif isinstance(input_type, str):
            value_type = input_type
        #     for field_ in input_type.fields or []:
        #         ...
        else:
            value_type = None
        if value_type is not None:
            prop = InformationProperty(
                class_=parent,
                name=item.display_name,
                description=item.description,
                property_=item.name,
                value_type=XSD_VALUE_TYPE_MAPPINGS[value_type],
            )
            self.properties.append(prop)
        else:
            self.issues.append(
                validation.UnknownProperty(
                    component_type=item.schema_.type if isinstance(item.schema_, DTDLBase) else str(item.schema_),
                    property_name="schema",
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )

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
                name=item.display_name,
                description=item.description,
                min_count=item.min_multiplicity,
                max_count=item.max_multiplicity,
                property_=item.name,
                value_type=ClassEntity.from_raw(item.target.as_class_id()),
            )
            self.properties.append(prop)
        elif item.properties is not None:
            for prop_ in item.properties or []:
                self.convert_property(prop_, parent)
