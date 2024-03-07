import json
import re
import warnings
from abc import ABC
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeAlias, overload

from pydantic import BaseModel, Field, field_validator, model_validator

from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty

from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.validation import IssueList, ValidationIssue
from cognite.neat.rules import validation
from cognite.neat.rules.importers._base import BaseImporter
from cognite.neat.rules._shared import Rules

from ._v3_spec import DTDLBase, DTMI




class DTDLImporter(BaseImporter):
    """Importer for DTDL (Digital Twin Definition Language) files. It can import a directory containing DTDL files and
    convert them to InformationRules.

    The DTDL v3 stanard is supported and defined at
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
            properties=SheetList(data=properties),
            classes=SheetList(data=classes),
        )

        return self._to_output(rules, errors, role)

    @classmethod
    def _to_triples(cls, item: DTDLBase, parent: str | None = None) -> tuple[list[InformationClass], list[InformationProperty], list[ValidationIssue]]:
        classes: list[InformationClass] = []
        properties: list[InformationProperty] = []
        issues: list[ValidationIssue] = []
        if isinstance(item, Interface):
            class_ = InformationClass(
                class_=item.display_name or item.id_,

        else:
            issues.append(validation.UnknownComponent(
                component_name=item.type,
                instance_name=item.display_name,
                instance_id=item.id_
            ))
        return classes, properties, issues

