from datetime import datetime, timezone
from typing import Any, Literal

import pandas as pd

from cognite.neat.rules.models.tables import Tables

from ._base import BaseImporter


class DictImporter(BaseImporter):
    """
    Importer for an arbitrary dictionary to tables.

    Args:
        data: dictionary containing Rules definitions.
        relationship_direction: Direction of relationships, either "parent-to-child" or "child-to-parent". Dictionaries
            are nested with children nested inside parents. This option determines whether the resulting rules
            will have an edge from parents to children or from children to parents.
    """

    def __init__(
        self,
        data: dict[str, Any],
        relationship_direction: Literal["parent-to-child", "child-to-parent"] = "parent-to-child",
    ):
        self.data = data
        self.relationship_direction = relationship_direction

    def to_tables(self) -> dict[str, pd.DataFrame]:
        metadata = pd.Series(
            dict(
                title="OpenAPI to DM transformation rules",
                description="OpenAPI to DM transformation rules",
                version="0.1",
                creator="Cognite",
                created=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                namespace="http://purl.org/cognite/neat#",
                prefix="neat",
                data_model_name="OpenAPI",
                cdf_space_name="OpenAPI",
            )
        ).reset_index()
        finder = _TripleFinder(self.relationship_direction)
        finder.find_triples(self.data)

        return {
            Tables.metadata: metadata,
            Tables.classes: pd.DataFrame(finder.classes).T,
            Tables.properties: pd.DataFrame(finder.properties).T,
        }


class _TripleFinder:
    def __init__(self, relationship_direction: Literal["parent-to-child", "child-to-parent"]) -> None:
        self.classes: dict[str, dict[str, Any]] = {}
        self.properties: dict[str, dict[str, Any]] = {}
        self.relationship_direction = relationship_direction

    def find_triples(self, data: dict[str, Any]) -> None:
        self._convert_dict_to_classes_and_props(data)

    def _convert_dict_to_classes_and_props(
        self, data: dict, parent_property_name: str | None = None, grand_parent_property_name: str | None = None
    ) -> None:
        if isinstance(data, dict) and len(data) == 0:
            return
        elif isinstance(data, dict) and parent_property_name is None:
            for key, value in data.items():
                self._convert_dict_to_classes_and_props(value, key)
        elif isinstance(data, dict):
            self.add_class(parent_property_name, "missing", grand_parent_property_name)
            for key, value in data.items():
                self._convert_dict_to_classes_and_props(value, key, parent_property_name)
        elif isinstance(data, list):
            for item in data:
                self._convert_dict_to_classes_and_props(item, parent_property_name, grand_parent_property_name)
        elif isinstance(data, bool | int | float | str) and parent_property_name is not None:
            data_type = {bool: "boolean", int: "integer", float: "float", str: "string"}[type(data)]
            self.add_property(grand_parent_property_name, parent_property_name, data_type, "missing")
        else:
            raise ValueError(f"Unknown type {type(data)}")

    def add_class(self, class_name: str, description: str = "", parent_class_name: str | None = None):
        if class_name in self.classes:
            return
        class_ = {"Class": class_name, "description": description}
        if parent_class_name:
            if self.relationship_direction == "child-to-parent":
                self.add_property(class_name, "parent", parent_class_name, "missing")
            elif self.relationship_direction == "parent-to-child":
                self.add_property(parent_class_name, class_name, class_name, "missing")
            else:
                raise ValueError(f"Unknown relationship direction {self.relationship_direction}")
        self.classes[class_name] = class_

    def add_property(self, class_name: str, property_name: str, property_type: str, description: str = "missing"):
        if class_name + property_name in self.properties:
            return
        prop = dict(
            class_id=class_name,
            property_id=property_name,
            property_name=property_name,
            property_type="ObjectProperty",
            description=description,
            expected_value_type=property_type,
            cdf_resource_type="Asset",
            resource_type_property="Asset",
            rule_type="rdfpath",
            rule=f"neat:{class_name}(neat:{property_name})",
            label="linked to",
        )
        self.properties[class_name + property_name] = prop
