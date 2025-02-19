from cognite.client.data_classes.data_modeling import ViewApply

from cognite.neat._cfihos.common.constants import (
    EntityStructure,
    PropertyStructure,
)


def create_schema_from_model_entities(
    entity_views: list[ViewApply], model_entities: dict, containers_space: str, parent_types: list[str]
) -> str:
    """
    Creates a data model GraphQL schema.

    Args:
        cdf_client (CogniteClient): The Cognite client to use for interacting with the data modeling API.
        space (str): The namespace or space identifier where the data model will reside.
        data_model_external_id (str): The external ID for the data model.
        data_model_name (str): The name of the data model.
        data_model_desc (str): A description of the data model.
        data_model_version (str): The version identifier for the data model.
        gql_schema (str): The GraphQL schema defining the data model.
    Notes:
        - This function sets up a GraphQL client with the appropriate configuration from the Cognite client.
        - It constructs a GraphQL mutation query to upsert the data model using the provided schema and parameters.
    Returns:
        dict: The response from the GraphQL API after attempting to upsert the data model.
    """
    gql_schema = ""
    for view in entity_views:
        if len(model_entities[view.external_id.replace("_", "-")][EntityStructure.PROPERTIES]) > 0:
            name = view.name
            desc = view.description.replace('"', "'")
            view_filter = (
                "rawFilter: {and : [{in: {property: "
                + f"{view.filter._filters[0]._property}, values: {view.filter._filters[0]._values}"
                + "}}]},"
                if view.filter and len(view.filter._filters[0]._values) > 0
                else ""
            )
            implements = (
                "implements " + (" & ".join([imp_view.external_id for imp_view in view.implements]))
                if view.implements
                else ""
            )
            has_child = True if view.external_id in parent_types else False
            type_str = (
                "interface" if has_child or view.external_id in ["CFIHOS_00000033", "CFIHOS_00000034"] else "type"
            )
            add_entity_str = (
                f'''
        """Entity Type
        @name entity_type"""
        entityType: String! @mapping(container: "EntityTypeGroup",property: "entityType", space: "{containers_space}")'''
                if implements != ""
                and not model_entities[view.external_id.replace("_", "-")][EntityStructure.FIRSTCLASSCITIZEN]
                else ""
            )
            properties = model_entities[view.external_id.replace("_", "-")][EntityStructure.PROPERTIES]
            property_str = ""
            for property in properties:
                # add the property mapping directive. If the property is custom added then it should be mapped to its defined mapping reference, else to the same propertyID in the relevent container
                mapping_str = f' @mapping(container: "{property[PropertyStructure.PROPERTY_GROUP]}", space: "{containers_space}", property: "{property[PropertyStructure.MAPPED_PROPERTY] if property[PropertyStructure.ID] != "entityType" and property[PropertyStructure.CUSTOM_PROPERTY] else property[PropertyStructure.ID]}")'
                property_str += f'''
        """{property[PropertyStructure.DESCRIPTION].replace('"',"'")}
        @name {property[PropertyStructure.NAME]}"""
        {property[PropertyStructure.ID]}: {property[PropertyStructure.TARGET_TYPE] + mapping_str}
                '''
            property_str += add_entity_str

            entity_str = f'''
    """{desc}
    @name {name} """

    {type_str} {view.external_id} {implements} @view({view_filter.replace("'",'"')} version:"{view.version}") {{
    {property_str}
    }}'''
            gql_schema += f"{entity_str}\n\n"

    return gql_schema
