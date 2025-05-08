from dataclasses import dataclass

from cognite.neat._cfihos.common.generic_classes import (
    EntityStructure,
    PropertyStructure,
)

from ..cfihos.constants import PARENT_SUFFIX

ENTITY_CDM_EXTENSION_MAPPING = {
    "CFIHOS ID": EntityStructure.ID,
    "inherited core model type": EntityStructure.IMPLEMENTS_CORE_MODEL,
}

ENTITY_COLUMN_MAPPING = {
    "name": EntityStructure.NAME,
    "definition": EntityStructure.DESCRIPTION,
    "parent CFIHOS unique ID": EntityStructure.INHERITS_FROM_ID,
    "parent entity name": EntityStructure.INHERITS_FROM_NAME,
    "is first class citizen": EntityStructure.FIRSTCLASSCITIZEN,
}

ENTITY_EDGE_COLUMN_MAPPING = {
    "source": PropertyStructure.EDGE_SOURCE,
    "destination": PropertyStructure.EDGE_TARGET,
    "edge unique id": PropertyStructure.ID,
    "edge name": PropertyStructure.NAME,
    "edge definition": PropertyStructure.DESCRIPTION,
    PropertyStructure.EDGE_EXTERNAL_ID: PropertyStructure.EDGE_EXTERNAL_ID,
}

ENTITY_EDGE_REVERSE_COLUMN_MAPPING = {
    "source": PropertyStructure.EDGE_TARGET,
    "destination": PropertyStructure.EDGE_SOURCE,
    "reverse edge unique id": PropertyStructure.ID,
    "reverse edge name": PropertyStructure.NAME,
    "reverse edge definition": PropertyStructure.DESCRIPTION,
    PropertyStructure.EDGE_EXTERNAL_ID: PropertyStructure.EDGE_EXTERNAL_ID,
}

ENTITY_PROPERTY_METADATA_MAPPING = {
    "CFIHOS unique id": PropertyStructure.ID,
    "name": PropertyStructure.NAME,
    "definition": PropertyStructure.DESCRIPTION,
    "format": PropertyStructure.TARGET_TYPE,
}

ENTITY_RAW_COLUMN_MAPPING = {
    EntityStructure.ID: "CFIHOS unique ID",
    EntityStructure.NAME: "name",
    EntityStructure.INHERITS_FROM_ID: "parent CFIHOS unique ID",
    EntityStructure.INHERITS_FROM_NAME: "parent entity name",
}

ENTITY_RELEVANT_PROPERTY_COLUMNS = {
    "entity CFIHOS unique id": EntityStructure.ID,
    "entity name": EntityStructure.NAME,
    "attribute CFIHOS unique id": PropertyStructure.ID,
    "attribute name": PropertyStructure.NAME,
    "constraint must be present in - name": PropertyStructure.PROPERTY_TYPE,
    "entity attribute definition": PropertyStructure.DESCRIPTION,
    "identifier / mandatory / optional": PropertyStructure.IS_REQUIRED,
    "CDF reverse property id": PropertyStructure.REV_THROUGH_PROPERTY,
    "CDF reverse property name": PropertyStructure.REV_PROPERTY_NAME,
    "CDF reverse property description": PropertyStructure.REV_PROPERTY_DESCRIPTION,
    "CDF isList": PropertyStructure.MULTI_VALUED,
}

TAG_OR_EQUIPMENT_PROPERTY_METADATA_MAPPING = {
    "CFIHOS unique id": PropertyStructure.ID,
    "property name": PropertyStructure.NAME,
    "property definition": PropertyStructure.DESCRIPTION,
    "property data type": PropertyStructure.TARGET_TYPE,
    "picklist name": PropertyStructure.ENUMERATION_TABLE,
    # TODO: Use this for UOM instead from entity properties in the future (CFIHOS V.1.5.?)
    "unit of measure dimension code": PropertyStructure.UOM,
}


@dataclass
class TagOrEquipment:
    """Tag or Equipment dataframe fields."""

    cfihos_type_object_name: str

    @property
    def column_renaming(self) -> dict[str, str]:
        """Column renaming for the Tag or Equipment dataframes."""
        return {
            f"{self.cfihos_type_object_name} class name": EntityStructure.NAME,
            f"{self.cfihos_type_object_name} class definition": EntityStructure.DESCRIPTION,
            f"{self.cfihos_type_object_name} class name{PARENT_SUFFIX}": EntityStructure.INHERITS_FROM_NAME,
            f"{EntityStructure.ID}{PARENT_SUFFIX}": EntityStructure.INHERITS_FROM_ID,
        }

    @property
    def raw_column_mapping(self) -> dict[str, str]:
        """Raw column mapping for the Tag or Equipment dataframes."""
        return {
            EntityStructure.ID: "CFIHOS unique id",
            EntityStructure.NAME: f"{self.cfihos_type_object_name} class name",
            "parent_name_key": f"parent {self.cfihos_type_object_name} class name",
            "parent_join_key": "parent_join_key",
            "entity_join_key": EntityStructure.ID,
        }

    @property
    def property_mapping(self) -> dict[str, str]:
        """Property mapping for the Tag or Equipment dataframes."""
        return {
            f"{self.cfihos_type_object_name} class CFIHOS unique id": EntityStructure.ID,
            f"{self.cfihos_type_object_name} class name": EntityStructure.NAME,
            f"{self.cfihos_type_object_name} property CFIHOS unique id": PropertyStructure.ID,
            f"{self.cfihos_type_object_name} property name": PropertyStructure.NAME,
            "SI unit of measure code": PropertyStructure.UOM,  # TODO - What should this be?
        }

    @property
    def parent_entity_id_column(self) -> str:
        """Parent entity ID column name."""
        return f"{EntityStructure.ID}_parent"

    @property
    def parent_entity_name_column(self) -> str:
        """Parent entity name column name."""
        return f"{self.cfihos_type_object_name} class name{PARENT_SUFFIX}"
