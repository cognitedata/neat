from datetime import datetime, timezone
from typing import Any, Literal

import pandas as pd

from cognite.neat.legacy.rules.models.tables import Tables

from ._base import BaseImporter


class ArbitraryDictImporter(BaseImporter):
    """
    Importer for an arbitrary dictionary.

    This importer infers the data model from the dictionary based on the shape of the data.

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
            self.add_class(parent_property_name, "missing", grand_parent_property_name, is_list=False)
            for key, value in data.items():
                self._convert_dict_to_classes_and_props(value, key, parent_property_name)
        elif isinstance(data, list):
            if parent_property_name is not None and grand_parent_property_name is not None:
                data_type = self._get_list_type(data, parent_property_name)
                self.add_property(grand_parent_property_name, parent_property_name, data_type, "missing", is_list=True)
            for item in data:
                self._convert_dict_to_classes_and_props(item, parent_property_name, grand_parent_property_name)
        elif isinstance(data, bool | int | float | str) and parent_property_name is not None:
            data_type = self._get_primitive_data_type(data)
            self.add_property(grand_parent_property_name, parent_property_name, data_type, "missing")
        else:
            raise ValueError(f"Unknown type {type(data)}")

    def add_class(
        self, class_name: str, description: str = "", parent_class_name: str | None = None, is_list: bool = False
    ):
        if class_name in self.classes:
            return
        class_ = {"Class": class_name, "description": description}
        if parent_class_name:
            if self.relationship_direction == "child-to-parent":
                self.add_property(class_name, "parent", parent_class_name, "missing", is_list=False)
            elif self.relationship_direction == "parent-to-child":
                self.add_property(parent_class_name, class_name, class_name, "missing", is_list)
            else:
                raise ValueError(f"Unknown relationship direction {self.relationship_direction}")
        self.classes[class_name] = class_

    def add_property(
        self,
        class_name: str,
        property_name: str,
        property_type: str,
        description: str = "missing",
        is_list: bool = False,
    ):
        if class_name + property_name in self.properties:
            return
        prop = dict(
            class_id=class_name,
            property_id=property_name,
            property_name=property_name,
            property_type="ObjectProperty",
            description=description,
            expected_value_type=property_type,
            max_count=1 if not is_list else None,
            cdf_resource_type="Asset",
            resource_type_property="Asset",
            rule_type="rdfpath",
            rule=f"neat:{class_name}(neat:{property_name})",
            label="linked to",
        )
        self.properties[class_name + property_name] = prop

    @staticmethod
    def _get_primitive_data_type(data: Any, errors: Literal["raise", "empty"] = "raise") -> str:
        data_type = type(data)
        if data_type is bool:
            return "boolean"
        elif data_type is int:
            return "integer"
        elif data_type is float:
            return "float"
        elif data_type is str and not pd.isna(pd.to_datetime(data, errors="coerce")):
            return "dateTime"
        elif data_type is str:
            return "string"

        if errors == "empty":
            return ""
        else:
            raise ValueError(f"Unknown primitive type {data_type}")

    @classmethod
    def _get_list_type(cls, data: list[Any], class_name: str) -> str:
        if isinstance(data[0], dict):
            return class_name

        data_types = {cls._get_primitive_data_type(item, "empty") for item in data}
        if "" in data_types or len(data_types) > 1:
            # Fallback to string
            return "string"
        return data_types.pop()
