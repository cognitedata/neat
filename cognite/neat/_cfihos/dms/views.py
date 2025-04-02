from cognite.client.data_classes import data_modeling
from cognite.client.data_classes.data_modeling import data_types

from cognite.neat._cfihos.common.constants import (
    EntityStructure,
    PropertyStructure,
)
from cognite.neat._cfihos.common.log import log_init
from cognite.neat._cfihos.common.utils import get_relation_target_if_eligible
from cognite.neat._rules.models.dms._rules import (
    DMSView,
)

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


def _build_inheritance_graph(entities: dict):
    """
    Builds an inheritance graph from a dictionary of entities. Each entity can inherit from multiple other entities,
    and the graph represents these inheritance relationships.

    Args:
        entities (dict): A dictionary where keys are entity IDs and values are dictionaries containing entity data.
                    The entity data dictionaries must contain entity ID key for the entity's unique identifier and
                    a `FULL_INHERITANCE` key, which maps to a dictionary of inherited entity IDs.

    Returns:
        dict: A dictionary representing the inheritance graph. The keys are entity IDs, and the values are sets of
              entity IDs that the key entity directly inherits from.
    """

    graph = {k: set() for k in entities}
    for key, value in entities.items():
        for ids in value[EntityStructure.FULL_INHERITANCE].values():
            for inherit_id in ids:
                for item_key, item_value in entities.items():
                    if item_value[EntityStructure.ID] == inherit_id:
                        graph[key].add(item_key)
                        break
    return graph


def _topological_sort(graph: dict):
    """
    Performs a topological sort on a directed acyclic graph (DAG). The sort orders the nodes such that for every
    directed edge u -> v, node u comes before node v in the ordering.

    Args:
        graph (dict): A dictionary representing a DAG. The keys are node IDs and the values are sets of neighboring
                      node IDs to which there are directed edges.
    Notes:
        - This function assumes that the input graph is a directed acyclic graph (DAG).
        - The function uses depth-first search (DFS) to perform the topological sort.
    Returns:
        list: A list of node IDs representing the topological order of the graph.
    """

    visited = set()
    stack = []

    def visit(node):
        if node not in visited:
            visited.add(node)
            for neighbor in graph[node]:
                visit(neighbor)
            stack.append(node)

    for node in graph:
        visit(node)

    return stack


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
    return {
        "and": [
            {
                "in": {
                    "property": [space, "EntityTypeGroup", "entityType"],
                    "values": list(
                        set(
                            list(
                                [
                                    id[1:] if id.startswith("ECFIHOS") or id.startswith("TCFIHOS") else id
                                    for id in inherited_entities
                                    if id
                                ]
                                + [
                                    id[1:] if id.startswith("ECFIHOS") or id.startswith("TCFIHOS") else id
                                    for id in list([entity_id])
                                ]
                            )
                        )
                    ),
                }
            }
        ]
    }


def create_views_from_containers(
    version: str, containers: list[data_modeling.ContainerApply], entities: dict
) -> list[data_modeling.ViewApply]:
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
    container_views = []
    for container in containers:
        v = data_modeling.ViewApply(
            space=container.space,
            external_id=container.external_id,
            version=version,
            name=entities[container.external_id.replace("_", "-")]["entityName"]
            if container.external_id.replace("_", "-") in entities.keys()
            else container.name,
            description=entities[container.external_id.replace("_", "-")]["description"]
            if container.external_id.replace("_", "-") in entities.keys()
            else container.description,
            implements=None,
            properties={
                key: data_modeling.MappedPropertyApply(
                    name=data.name.strip() if data.name else None,
                    description=data.description.strip() if data.description else None,
                    container=data_modeling.ContainerId(space=container.space, external_id=container.external_id),
                    source=data_modeling.ViewId(
                        space=container.space,
                        external_id=relation_target,
                        version=version,
                    )
                    if relation_target is not None
                    else None,
                    container_property_identifier=key,
                )
                for key, data in container.properties.items()
                for relation_target in [
                    get_relation_target_if_eligible(key, container.external_id.replace("_", "-"), entities, data.type)
                ]
            },
        )

        # edges and reverse direct relation do not have container, thus they are added from entities
        if container.external_id.replace("_", "-") in entities.keys():
            for prop in entities[container.external_id.replace("_", "-")]["properties"]:
                # if its an edge
                if prop[PropertyStructure.PROPERTY_TYPE] == PropertyStructure.ENTITY_EDGE:
                    v.properties[prop[PropertyStructure.ID]] = data_modeling.MultiEdgeConnectionApply(
                        name=prop[PropertyStructure.NAME],
                        # description=prop[PropertyStructure.DESCRIPTION],
                        direction=prop[PropertyStructure.EDGE_DIRECTION],
                        type=data_modeling.DirectRelationReference(
                            space=container.space,
                            external_id=prop[PropertyStructure.EDGE_EXTERNAL_ID],
                        ),
                        source=data_modeling.ViewId(
                            space=container.space,
                            external_id=prop[PropertyStructure.EDGE_TARGET],
                            version=version,
                        ),
                    )
                # if its a reverse direct relation

        # TODO: Quick fix to add entityType to every view
        if (
            container.external_id.replace("_", "-") not in entities.keys()
            or not entities[container.external_id.replace("_", "-")][EntityStructure.FIRSTCLASSCITIZEN]
        ):
            v.properties["entityType"] = data_modeling.MappedPropertyApply(
                name="entity type",
                description=None,
                container=data_modeling.ContainerId(
                    space=container.space,
                    external_id="EntityTypeGroup",
                ),
                source=None,
                container_property_identifier="entityType",
            )
        container_views.append(v)

    # TODO: implement Dry run
    # cdf_client.data_modeling.views.apply(container_views)
    # space = container_views[0].space
    # logging.info(f"Upserted {len(container_views)} container views to space {space}")
    return container_views


def build_views_from_containers(version: str, containers: list[data_modeling.ContainerApply], entities: dict) -> any:
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
    container_views = []
    lst_properties = []
    lst_views = []
    views_dict = {}
    lst_dms_properties = [DMSView]
    for container in containers:
        lst_views.append(
            {
                "View": container["Container"],
                "Name": entities[container["Container"].replace("_", "-")]["entityName"]
                if container["Container"].replace("_", "-") in entities.keys()
                else "",
                "Description": entities[container["Container"].replace("_", "-")]["description"]
                if container["Container"].replace("_", "-") in entities.keys()
                else "",
                "Implements": None,
                "Filter": None,
                "In Model": True,
                "Class (linage)": container["Container"],
            }
        )

        for key, data in container["Properties"].items():
            relation_target = get_relation_target_if_eligible(
                key, container["Container"].replace("_", "-"), entities, data.type
            )
            # lst_dms_properties.append(DMSView(View=container["Container"],
            #         view: key,
            #         Name: "",
            #         "Description": data.description.strip() if data.description else "",
            #         "Connection": "direct" if type(data.type) == data_types.DirectRelation else "edge" if data.type._type == PropertyStructure.Direct_Relation else "",
            #         "Value Type": map_property_type[str(data.type)] if type(data.type) != data_types.DirectRelation else relation_target,
            #         "Nullable": data.nullable,
            #         "Immutable": False,
            #         "Is List": data.type.is_list,
            #         "Default": "",
            #         "Reference": "",
            #         "Container": container["Container"],
            #         "Container Property": key,
            #         "Index": "",
            #         "Constraint": "",
            #         "Class (linage)": container["Container"],
            #         "Property (linage)": key,
            # )
            #   ))
            lst_properties.append(
                {
                    "View": container["Container"],
                    "View Property": key,
                    "Name": "",
                    "Description": data.description.strip() if data.description else "",
                    "Connection": "direct"
                    if type(data.type) == data_types.DirectRelation
                    else "edge"
                    if data.type._type == PropertyStructure.Direct_Relation
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

    # TODO: implement Dry run
    # cdf_client.data_modeling.views.apply(container_views)
    # space = container_views[0].space
    # logging.info(f"Upserted {len(container_views)} container views to space {space}")
    return lst_views, lst_properties


def build_views_from_entities(
    views_space: str, containers_space: str, version: str, entities: dict
) -> tuple[list[data_modeling.ViewApply], list[str]]:
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
    inheritance_tree = _create_inheritance_tree_from_root_node(
        entities=entities
    )  # TODO: use build_inheritance_graph() instead
    dm_views = []
    inheritance_graph = _build_inheritance_graph(entities)
    sorted_keys = _topological_sort(inheritance_graph)
    sorted_hierarchy_entities = {k: entities[k] for k in sorted_keys if k in entities}
    lst_views = []
    lst_properties = []
    for _, entity_data in sorted_hierarchy_entities.items():
        entity_id = entity_data[EntityStructure.ID]
        parents_ext_ids = [
            parent_id
            for parent_ids in entity_data[EntityStructure.FULL_INHERITANCE].values()
            for parent_id in parent_ids
        ]
        view_filter = _create_view_filter(containers_space, entity_id, inheritance_tree.get(entity_id, []))



        prop_data_dict = {}
        for prop_data in entity_data[EntityStructure.PROPERTIES]:
            # if prop_data[PropertyStructure.INHERITED] is False:
            if prop_data[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION":
                prop_data_dict[prop_data[PropertyStructure.ID]] = data_modeling.MappedPropertyApply(
                    name=prop_data[PropertyStructure.NAME],
                    description=prop_data[PropertyStructure.DESCRIPTION],
                    container=data_modeling.ContainerId(
                        space=containers_space,
                        external_id=prop_data[PropertyStructure.PROPERTY_GROUP],
                    ),
                    container_property_identifier=prop_data[PropertyStructure.ID],
                    source=data_modeling.ViewId(
                        space=containers_space,
                        external_id=prop_data[PropertyStructure.TARGET_TYPE],
                        version=version,
                    ),
                )

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
                        "Property (linage)": prop_data[PropertyStructure.ID].replace("_rel", ""),
                    }
                )

                prop_data_dict[prop_data[PropertyStructure.ID].replace("_rel", "")] = data_modeling.MappedPropertyApply(
                    name=prop_data[PropertyStructure.NAME],
                    description=prop_data[PropertyStructure.DESCRIPTION],
                    container=data_modeling.ContainerId(
                        space=containers_space, external_id=prop_data[PropertyStructure.PROPERTY_GROUP]
                    ),
                    container_property_identifier=prop_data[PropertyStructure.ID].replace("_rel", ""),
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
                # to fix
                prop_data_dict[prop_data[PropertyStructure.ID].replace("_rel", "")] = data_modeling.MappedPropertyApply(
                    name=prop_data[PropertyStructure.NAME],
                    description=prop_data[PropertyStructure.DESCRIPTION],
                    container=data_modeling.ContainerId(
                        space=containers_space,
                        external_id=prop_data[PropertyStructure.PROPERTY_GROUP],
                    ),
                    container_property_identifier=prop_data[PropertyStructure.ID].replace("_rel", ""),
                )

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
                prop_data_dict["entityType"] = data_modeling.MappedPropertyApply(
                    name="Entity Type",
                    container=data_modeling.ContainerId(
                        space=containers_space,
                        external_id="EntityTypeGroup",
                    ),
                    container_property_identifier="entityType",
                )

        # Avoid creating views for types without properties - e.g: empty abstract classes
        if len(entity_data[EntityStructure.PROPERTIES]) > 0:
            lst_views.append(
                {
                    "View": entity_data[EntityStructure.ID],
                    "Name": entity_data[EntityStructure.NAME],
                    "Description": entity_data[EntityStructure.DESCRIPTION],
                    "Implements": [parent_id for parent_id in parents_ext_ids] if parents_ext_ids else None,
                    "Filter": view_filter
                    if view_filter and not entity_data[EntityStructure.FIRSTCLASSCITIZEN]
                    else None,
                    "In Model": True,
                    "Class (linage)": entity_data[EntityStructure.ID],
                }
            )

            dm_view = data_modeling.ViewApply(
                space=views_space,
                external_id=entity_data[EntityStructure.ID],
                version=version,
                name=entity_data[EntityStructure.NAME],
                description=entity_data[EntityStructure.DESCRIPTION],
                filter=data_modeling.Filter.load(view_filter)
                if view_filter and not entity_data[EntityStructure.FIRSTCLASSCITIZEN]
                else None,
                implements=[
                    data_modeling.ViewId(space=views_space, external_id=parent_id, version=version)
                    for parent_id in parents_ext_ids
                ]
                if parents_ext_ids
                else None,
                properties=prop_data_dict,
            )
            dm_views.append(dm_view)
        else:
            logging.warning(
                f"no properties assinged to {entity_data[EntityStructure.ID]}. The view will not be created"
            )

    # logging.info(f"built {len(dm_views)} scoped data model views")
    # # TODO: enable views batching
    # cdf_client.data_modeling.views.apply(dm_views)
    # logging.info(f"Upserted {len(dm_views)} scoped data model views to space {views_space}")

    # Use chunks of 100 instead
    # for i in range(0, len(dm_views), 100):
    #     cdf_client.data_modeling.views.apply(dm_views[i:i+100])
    # TODO: implement Dry run
    return lst_views, lst_properties