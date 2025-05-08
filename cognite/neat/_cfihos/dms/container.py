from cognite.client.data_classes import data_modeling
from cognite.client.data_classes.data_modeling import data_types

from cognite.neat._cfihos.common.constants import CONTAINER_PROPERTY_LIMIT
from cognite.neat._cfihos.common.generic_classes import (
    PropertyStructure,
)
from cognite.neat._cfihos.common.log import log_init

logging = log_init(f"{__name__}", "i")

map_property_type = {
    "String": data_types.Text(),
    "Int": data_types.Int32(),
    "Float32": data_types.Float32(),
    "Boolean": data_types.Boolean(),
    "Timestamp": data_types.Timestamp(),
}


#  Need to convert dict to be by property group
def create_container_from_property_struct_dict(
    space: str,
    property_data: dict[str, dict],
    containers_indexes: list[dict[str, list[str]]],
) -> tuple[list[data_modeling.ContainerApply], list[str]]:
    """
    Creates data model containers from a dictionary of property structures. This function organizes properties into
    containers, applies indexing where necessary, and publishes the containers to the specified space.

    Args:
        space (str): The space identifier where the containers will reside.
        property_data (dict[str, dict]): A dictionary containing property information, keyed by property ID.
        containers_indexes (list[dict[str, list[str]]]): A list of dictionaries specifying indexes for the containers.
    Notes:
        - The function organizes properties into groups based on the PROPERTY_GROUP field.
        - It raises a ValueError if any group exceeds the maximum allowed number of properties or if a group has no properties.
        - Indexes are applied to the properties as specified in the containers_indexes argument initialzed in the configuration file.
        - An additional container for the entity type group is added with a default entityType property.
    Returns:
        Tuple[list[data_modeling.ContainerApply], list[str]]: A tuple containing a list of created ContainerApply
        objects and a list of the external IDs of all parent entities.

    """
    containers = []
    property_groups = {}

    for prop_id, prop_row in property_data.items():
        # prop_row[PropertyStructure.ID] = prop_id
        property_groups.setdefault(prop_row[PropertyStructure.PROPERTY_GROUP], [])

        # remove edges and reverse direct relations as they will not have containers
        if prop_row[PropertyStructure.PROPERTY_TYPE] != PropertyStructure.ENTITY_EDGE:
            property_groups[prop_row[PropertyStructure.PROPERTY_GROUP]].append(prop_row)

    for property_group, properties in property_groups.items():
        if len(properties) > CONTAINER_PROPERTY_LIMIT:
            raise ValueError(
                f"Container group is given {len(properties)}, but can maximum have {CONTAINER_PROPERTY_LIMIT} properties"
            )
        if len(properties) == 0:
            raise ValueError(f"Container must have properties, but 0 was given for group {property_group}")

        container_indexes_dict = {}
        properties_dict = {}

        for prop in properties:
            property_type = (
                data_modeling.DirectRelation()
                if prop[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION"
                else map_property_type[prop[PropertyStructure.TARGET_TYPE]]
            )
            properties_dict[prop[PropertyStructure.ID]] = data_modeling.ContainerProperty(
                type=property_type,
                nullable=True,
                auto_increment=False,
                name=prop[PropertyStructure.NAME],
                default_value=None,
                description=None,
            )
            if property_group in containers_indexes.keys():
                for container_index in containers_indexes[property_group]:
                    if prop[PropertyStructure.ID] in container_index["properties"]:
                        if container_index["index_type"] == "BTreeIndex":
                            container_indexes_dict[container_index["index_id"]] = data_modeling.containers.BTreeIndex(
                                properties=[prop[PropertyStructure.ID]], cursorable=False
                            )
                        elif container_index["index_type"] == "InvertedIndex":
                            container_indexes_dict[container_index["index_id"]] = (
                                data_modeling.containers.InvertedIndex(
                                    properties=[prop[PropertyStructure.ID]], cursorable=False
                                )
                            )
        containers.append(
            {
                "Container": property_group,
                "Name": "",
                "Description": "",
                "Constraint": "",
                "Class (linage)": property_group,
                "Properties": properties_dict,
            }
        )

    # TODO: Quick fix to handling entity type
    containers.append(
        {
            "Container": "EntityTypeGroup",
            "Name": "",
            "Description": "",
            "Constraint": "",
            "Class (linage)": "EntityTypeGroup",
            "Properties": {
                "entityType": data_modeling.ContainerProperty(
                    type=data_types.Text(),
                    nullable=False,
                    auto_increment=False,
                    name="entity_type",
                    default_value=None,
                    description=None,
                )
            },
        }
    )

    return containers
