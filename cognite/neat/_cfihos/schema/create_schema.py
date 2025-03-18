from cognite.client.data_classes.data_modeling import ViewApply


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

    return ""
