import json
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, overload

from cognite.neat.rules import validation
from cognite.neat.rules._shared import Rules
from cognite.neat.rules.importers._base import BaseImporter
from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules._types import ClassEntity, ParentClassEntity, XSDValueType
from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty
from cognite.neat.rules.validation import IssueList, ValidationIssue

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
        self._item_by_id: dict[DTMI, DTDLBase] = {item.id_: item for item in items if item.id_}

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
        issues = IssueList([])
        properties: list[InformationProperty] = []
        classes: list[InformationClass] = []

        for item in self._items:
            item_classes, item_properties, item_issues = self._to_triples(item)
            classes.extend(item_classes)
            properties.extend(item_properties)
            issues.extend(item_issues)

        rules = InformationRules(
            metadata=self._default_metadata(),
            properties=SheetList[InformationProperty](data=properties),
            classes=SheetList[InformationClass](data=classes),
        )

        return self._to_output(rules, issues, errors, role)

    def _to_triples(
        self, item: DTDLBase, parent: str | None = None
    ) -> tuple[list[InformationClass], list[InformationProperty], list[ValidationIssue]]:
        classes: list[InformationClass] = []
        properties: list[InformationProperty] = []
        issues: list[ValidationIssue] = []
        if isinstance(item, Interface):
            class_ = InformationClass(
                class_=item.id_.as_class_id(),
                name=item.display_name,
                parent=[ParentClassEntity.from_raw(parent.as_class_id()) for parent in item.extends or []],
            )
            classes.append(class_)
            for subitem in item.contents or []:
                subitem_ = self._item_by_id.get(subitem) if isinstance(subitem, DTMI) else subitem
                if subitem_ is None:
                    issues.append(
                        validation.UnknownProperty(
                            component_type=item.type if isinstance(item, DTDLBase) else item,
                            property_name=subitem.type if isinstance(subitem, DTDLBase) else str(subitem),
                            instance_name=item.display_name,
                            instance_id=item.id_.model_dump() if item.id_ else None,
                        )
                    )
                    continue
                sub_classes, sub_properties, sub_issues = self._to_triples(subitem_, class_.class_)
                classes.extend(sub_classes)
                properties.extend(sub_properties)
                issues.extend(sub_issues)
            for subitem in item.schemas or []:
                issues.append(
                    validation.UnknownProperty(
                        component_type=item.type,
                        property_name=subitem.type,
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump() if item.id_ else None,
                    )
                )
        elif isinstance(item, Property):
            if parent is None:
                issues.append(
                    validation.MissingParentDefinition(
                        component_type=item.type,
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump() if item.id_ else None,
                    )
                )
                return classes, properties, issues
            input_type = self._item_by_id.get(item.schema_) if isinstance(item.schema_, DTMI) else item.schema_
            if isinstance(input_type, Enum):
                value_type = "string"
            elif isinstance(input_type, str):
                value_type = input_type
            else:
                value_type = None
            if value_type is not None:
                prop = InformationProperty(
                    class_=parent,
                    name=item.display_name,
                    description=item.description,
                    property_=item.name,
                    value_type=XSDValueType.from_string(value_type),
                )
                properties.append(prop)
            else:
                issues.append(
                    validation.UnknownProperty(
                        component_type=item.schema_.type if isinstance(item.schema_, DTDLBase) else str(item.schema_),
                        property_name="schema",
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump() if item.id_ else None,
                    )
                )
        elif isinstance(item, Relationship) and item.target is not None:
            if parent is None:
                issues.append(
                    validation.MissingParentDefinition(
                        component_type=item.type,
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump() if item.id_ else None,
                    )
                )
                return classes, properties, issues
            prop = InformationProperty(
                class_=parent,
                name=item.display_name,
                description=item.description,
                min_count=item.minMultiplicity,
                max_count=item.maxMultiplicity,
                property_=item.name,
                value_type=ClassEntity.from_string(item.target.model_dump()),
            )
            properties.append(prop)
        elif isinstance(item, Relationship) and item.properties is not None:
            for prop__ in item.properties or []:
                sub_classes, sub_properties, sub_issues = self._to_triples(prop__, parent)
                classes.extend(sub_classes)
                properties.extend(sub_properties)
                issues.extend(sub_issues)
        else:
            issues.append(
                validation.UnknownComponent(
                    component_type=item.type if isinstance(item, DTDLBase) else str(item),
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
        return classes, properties, issues
