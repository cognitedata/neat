import json

from cognite.client import CogniteClient
from cognite.client.data_classes import data_modeling
from cognite.client.data_classes.data_modeling import data_types
from cognite.client.exceptions import CogniteAPIError

from cognite.neat._cfihos.common.constants import (
    EntityStructure,
    PropertyStructure,
)
from cognite.neat._cfihos.common.log import log_init
from cognite.neat._cfihos.common.utils import get_relation_target_if_eligible

logging = log_init(f"{__name__}", "i")


def _create_inheritance_tree_from_root_node(entities: dict) -> dict:
    """
    Creates an inheritance tree from a dictionary of entities, starting from the root entities,
    where each entity may inherit from one or more parent entities.

    Args:
        entities (dict): A dictionary where keys are entity IDs and values are dictionaries containing entity data.
                         The entity data dictionaries must contain an `INHERITS_FROM_ID` key, which maps to a list of
                         parent entity IDs, and an entity ID key, which maps to the entity's unique identifier.

    Returns:
        dict: A dictionary representing the inheritance tree. The keys are parent entity IDs and the values are lists
              of all descendant entity IDs.
    """
    parent_child_dict = {}
    for entity_id, entity_data in entities.items():
        if entity_data[EntityStructure.INHERITS_FROM_ID]:
            for inheritance_id in entity_data[EntityStructure.INHERITS_FROM_ID]:
                try:
                    parent_child_dict[inheritance_id].add(entity_data[EntityStructure.ID])
                except KeyError:
                    parent_child_dict[inheritance_id] = set()
                    parent_child_dict[inheritance_id].add(entity_data[EntityStructure.ID])

    def visit(childs, parent_child_dict, inheritance_tree, found_childs):
        for child in childs:
            found_childs.add(child)
            if child in inheritance_tree:
                found_childs.update(set(inheritance_tree[child]))
                continue
            if parent_child_dict.get(child):
                visit(parent_child_dict[child], parent_child_dict, inheritance_tree, found_childs)
        return

    inheritance_tree = {}
    for entity_id, children in parent_child_dict.items():
        found_children = set()
        visit(children, parent_child_dict, inheritance_tree, found_children)
        inheritance_tree[entity_id] = list(found_children)
    return inheritance_tree


def _create_view_filter(space: str, entity_id: str, inherited_entities: list[str]) -> dict:
    """
    Creates a view filter for an entity in a given space, incorporating inherited entities. The filter is used to
    determine which entities should be included based on their IDs and type groups.

    Args:
        space (str): The space identifier where the entities reside.
        entity_id (str): The unique identifier of the entity.
        inherited_entities (list[str]): A list of inherited entity IDs.

    Returns:
        dict: A dictionary representing the view filter in the form of a nested dictionary structure.

    """

    return (
        "rawFilter("
        + json.dumps(
            {
                "and": [
                    {
                        "in": {
                            "property": [space, "EntityTypeGroup", "entityType"],
                            "values": list(
                                set(
                                    [
                                        id[1:] if id.startswith("ECFIHOS") or id.startswith("TCFIHOS") else id
                                        for id in inherited_entities
                                        if id
                                    ]
                                    + [
                                        entity_id[1:]
                                        if entity_id.startswith("ECFIHOS") or entity_id.startswith("TCFIHOS")
                                        else entity_id
                                    ]
                                )
                            ),
                        }
                    }
                ]
            }
        )
        + ")"
    )


def create_has_data_filter(container_space: str, container_external_id: str) -> dict:
    """
    Creates a filter for a specific container in a given space. The filter is used to determine which entities should
    be included based on their presence in the specified container.
    Args:
        container_space (str): The space identifier where the container resides.
        container_external_id (str): The unique identifier of the container.
    Returns:
        dict: A dictionary representing the filter in the form of a nested dictionary structure.
    """
    # return {
    #     "and": [
    #         {
    #             "hasData": [
    #                 {
    #                     "type": "container",
    #                     "space": container_space,
    #                     "externalId": container_external_id,
    #                 }
    #             ]
    #         }
    #     ]
    # }
    return None


def build_views_from_containers(containers: list[data_modeling.ContainerApply], entities: dict) -> any:
    """
    Creates a set of views that are one-to-one with the given containers. This function constructs views based on the
    properties of each container and the associated entity information.

    Args:
        version (str): The version identifier for the views being created.
        containers (list[data_modeling.ContainerApply]): A list of container objects to create views for.
        entities (dict): A dictionary containing entity information, keyed by entity external ID with underscores replaced by hyphens.

    Returns:
        list of created ViewApply objects.
    """
    map_property_type = {
        str(data_types.Text()): "text",
        str(data_types.Int32()): "int32",
        str(data_types.Float32()): "float32",
        str(data_types.Float64()): "float64",
        str(data_types.Boolean()): "boolean",
        str(data_types.Timestamp()): "timestamp",
    }
    lst_properties = []
    lst_views = []
    for container in containers:
        cdm_implements = (
            [view_id["external_id"] for view_id in container["Container"][EntityStructure.IMPLEMENTS_CORE_MODEL]]
            if entities.get(container["Container"], {}).get(EntityStructure.IMPLEMENTS_CORE_MODEL, None) is not None
            else None
        )

        lst_views.append(
            {
                "View": container["Container"],
                "Name": entities[container["Container"].replace("_", "-")]["entityName"]
                if container["Container"].replace("_", "-") in entities.keys()
                else "",
                "Description": entities[container["Container"].replace("_", "-")]["description"]
                if container["Container"].replace("_", "-") in entities.keys()
                else "",
                "Implements": ",".join(cdm_implements) if cdm_implements else None,
                "Filter": None,
                "In Model": True,
                "Class (linage)": container["Container"],
            }
        )

        for key, data in container["Properties"].items():
            relation_target = get_relation_target_if_eligible(
                key, container["Container"].replace("_", "-"), entities, data.type
            )
            lst_properties.append(
                {
                    "View": container["Container"],
                    "View Property": key,
                    "Name": "",
                    "Description": data.description.strip() if data.description else "",
                    "Connection": "direct"
                    if type(data.type) == data_types.DirectRelation
                    else "edge"
                    if data.type._type == PropertyStructure.DIRECT_RELATION
                    else None,
                    "Value Type": map_property_type[str(data.type)]
                    if type(data.type) != data_types.DirectRelation
                    else relation_target,
                    "Nullable": data.nullable,
                    "Immutable": False,
                    "Is List": data.type.is_list,
                    "Default": None,
                    "Reference": None,
                    "Container": container["Container"],
                    "Container Property": key,
                    "Index": None,
                    "Constraint": None,
                    "Class (linage)": container["Container"],
                    "Property (linage)": key,
                }
            )

        # # edges and reverse direct relation do not have container, thus they are added from entities
        # if container.external_id.replace("_", "-") in entities.keys():
        #     for prop in entities[container.external_id.replace("_", "-")]["properties"]:
        #         # if its an edge
        #         if prop[PropertyStructure.PROPERTY_TYPE] == PropertyStructure.ENTITY_EDGE:
        #             v.properties[prop[PropertyStructure.ID]] = data_modeling.MultiEdgeConnectionApply(
        #                 name=prop[PropertyStructure.NAME],
        #                 # description=prop[PropertyStructure.DESCRIPTION],
        #                 direction=prop[PropertyStructure.EDGE_DIRECTION],
        #                 type=data_modeling.DirectRelationReference(
        #                     space=container.space,
        #                     external_id=prop[PropertyStructure.EDGE_EXTERNAL_ID],
        #                 ),
        #                 source=data_modeling.ViewId(
        #                     space=container.space,
        #                     external_id=prop[PropertyStructure.EDGE_TARGET],
        #                     version=version,
        #                 ),
        #             )
        #         # if its a reverse direct relation

        # TODO: Quick fix to add entityType to every view
        if (
            container["Container"].replace("_", "-") not in entities.keys()
            or not entities[container["Container"].replace("_", "-")][EntityStructure.FIRSTCLASSCITIZEN]
        ) and container["Container"] != "EntityTypeGroup":
            lst_properties.append(
                {
                    "View": container["Container"],
                    "View Property": "entityType",
                    "Name": "",
                    "description": "",
                    "Connection": None,
                    "Value Type": "text",
                    "Nullable": False,
                    "Immutable": False,
                    "Is List": False,
                    "Default": None,
                    "Reference": None,
                    "Container": "EntityTypeGroup",
                    "Container Property": "entityType",
                    "Index": None,
                    "Constraint": None,
                    "Class (linage)": container["Container"],
                    "Property (linage)": "entityType",
                }
            )

    return lst_views, lst_properties


def build_views_from_entities(containers_space: str, entities: dict) -> tuple[list[data_modeling.ViewApply], list[str]]:
    """
    Builds a list of data model views from the provided entities. This function creates views that represent the
    entities, incorporating their properties and inheritance structures.

    Args:
        views_space (str): The space identifier where the views will reside.
        containers_space (str): The space identifier where the containers reside.
        version (str): The version identifier for the views being created.
        entities (dict): A dictionary containing entity information.
    Notes:
        - This function first builds an inheritance tree and graph from the entities.
        - It then performs a topological sort on the inheritance graph to determine the order of processing.
        - The view filter will be create and assigned to each view
        - Views are created by mapping entity properties and adding additional metadata from the entities dictionary.
        - If an entity does not have any properties, a warning is logged, and no view is created for that entity.
    Returns:
        Tuple[list[data_modeling.ViewApply], list[str]]: A tuple containing a list of created ViewApply objects and
        a list of the external IDs of all parent entities.
    """
    inheritance_tree = _create_inheritance_tree_from_root_node(entities=entities)
    lst_views = []
    lst_properties = []
    for _, entity_data in entities.items():
        entity_id = entity_data[EntityStructure.ID]
        parents_ext_ids = [
            parent_id
            for parent_ids in entity_data[EntityStructure.FULL_INHERITANCE].values()
            for parent_id in parent_ids
        ]

        # add views for those entities that implements core models
        parents_ext_ids.extend = (
            [view_id["version"] for view_id in entity_data[EntityStructure.IMPLEMENTS_CORE_MODEL]]
            if entity_data[EntityStructure.IMPLEMENTS_CORE_MODEL] is not None
            else []
        )

        view_filter = (
            create_has_data_filter(containers_space, entity_id)
            if entity_data[EntityStructure.FIRSTCLASSCITIZEN]
            else _create_view_filter(containers_space, entity_id, inheritance_tree.get(entity_id, []))
        )

        prop_data_dict = {}
        for prop_data in entity_data[EntityStructure.PROPERTIES]:
            # if prop_data[PropertyStructure.INHERITED] is False:
            if prop_data[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION":
                lst_properties.append(
                    {
                        "View": entity_data[EntityStructure.ID],
                        "View Property": prop_data[PropertyStructure.ID],
                        "Name": prop_data[PropertyStructure.NAME],
                        "Description": prop_data[PropertyStructure.DESCRIPTION],
                        "Connection": "direct",
                        "Value Type": prop_data[PropertyStructure.TARGET_TYPE],
                        "Nullable": True,
                        "Immutable": False,
                        "Is List": False,
                        "Default": None,
                        "Reference": None,
                        "Container": containers_space + ":" + prop_data[PropertyStructure.PROPERTY_GROUP],
                        "Container Property": prop_data[PropertyStructure.ID],
                        "Index": None,
                        "Constraint": None,
                        "Class (linage)": containers_space + ":" + prop_data[PropertyStructure.PROPERTY_GROUP],
                        "Property (linage)": prop_data[PropertyStructure.ID],
                    }
                )

            # # Edge support for query views
            # elif prop_data[PropertyStructure.PROPERTY_TYPE] == PropertyStructure.ENTITY_EDGE:
            #     prop_data_dict[prop_data[PropertyStructure.ID]] = data_modeling.MultiEdgeConnectionApply(
            #         name=prop_data[PropertyStructure.NAME],
            #         description=prop_data[PropertyStructure.DESCRIPTION],
            #         direction=prop_data[PropertyStructure.EDGE_DIRECTION],
            #         type=data_modeling.DirectRelationReference(
            #             space=views_space,
            #             external_id=prop_data[PropertyStructure.EDGE_EXTERNAL_ID],
            #         ),
            #         source=data_modeling.ViewId(
            #             space=views_space,
            #             external_id=prop_data[PropertyStructure.EDGE_TARGET],
            #             version=version,
            #         ),
            #     )

            else:
                lst_properties.append(
                    {
                        "View": entity_data[EntityStructure.ID],
                        "View Property": prop_data[PropertyStructure.ID].replace("_rel", ""),
                        "Name": prop_data[PropertyStructure.NAME],
                        "Description": prop_data[PropertyStructure.DESCRIPTION],
                        "Connection": None,
                        "Value Type": "text",
                        "Nullable": True,
                        "Immutable": False,
                        "Is List": False,
                        "Default": None,
                        "Reference": None,
                        "Container": containers_space + ":" + prop_data[PropertyStructure.PROPERTY_GROUP],
                        "Container Property": prop_data[PropertyStructure.ID].replace("_rel", ""),
                        "Index": None,
                        "Constraint": None,
                        "Class (linage)": containers_space + ":" + prop_data[PropertyStructure.PROPERTY_GROUP],
                        "Property (linage)": prop_data[PropertyStructure.PROPERTY_GROUP],
                    }
                )

        # add entityType property in case the entity is not FCC
        if view_filter and not entity_data[EntityStructure.FIRSTCLASSCITIZEN]:
            lst_properties.append(
                {
                    "View": entity_data[EntityStructure.ID],
                    "View Property": "entityType",
                    "Name": "Entity Type",
                    "Description": "",
                    "Connection": None,
                    "Value Type": "text",
                    "Nullable": False,
                    "Immutable": False,
                    "Is List": False,
                    "Default": None,
                    "Reference": None,
                    "Container": containers_space + ":EntityTypeGroup",
                    "Container Property": "entityType",
                    "Index": None,
                    "Constraint": None,
                    "Class (linage)": containers_space + ":EntityTypeGroup",
                    "Property (linage)": "entityType",
                }
            )

        # Avoid creating views for types without properties - e.g: empty abstract classes
        if len(entity_data[EntityStructure.PROPERTIES]) > 0:
            lst_views.append(
                {
                    "View": entity_data[EntityStructure.ID],
                    "Name": entity_data[EntityStructure.NAME],
                    "Description": entity_data[EntityStructure.DESCRIPTION],
                    "Implements": ",".join(parents_ext_ids) if parents_ext_ids else None,
                    "Filter": view_filter if view_filter else None,
                    "In Model": True,
                    "Class (linage)": entity_data[EntityStructure.ID],
                }
            )
        else:
            logging.warning(
                f"no properties assinged to {entity_data[EntityStructure.ID]}. The view will not be created"
            )
    return lst_views, lst_properties


def add_core_views(
    cdf_client: CogniteClient,
    original_views: list[data_modeling.ViewApply | data_modeling.ViewId],
) -> list[data_modeling.ViewApply | data_modeling.ViewId]:
    """Adds core views to the list of views.

    This function appends the core views to the existing views list.

    Args:
        cdf_client (CogniteClient): The Cognite client connection.
        original_views (list[data_modeling.ViewApply | data_modeling.ViewId]):
            The list of views to which core views will be added.

    Returns:
        list[data_modeling.ViewApply | data_modeling.ViewId]: The updated list of views.
    """
    try:
        core_views = cdf_client.data_modeling.views.list(space="cdf_cdm", include_global=True, limit=-1).as_ids()
        logging.info(f"Adding {len(core_views)} core views to the list of data model views.")
        original_views.extend(core_views)
    except CogniteAPIError as e:
        logging.error(f"Error retrieving core views: {e}")
        raise e
    return original_views
