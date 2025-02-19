# from cognite.client import CogniteClient
# from cognite.client.data_classes import data_modeling

# from cognite.neat._cfihos.common.graphql import (
#     execute_gql_query,
#     setup_gql_client,
# )
# from cognite.neat._cfihos.common.log import log_init

# logging = log_init(f"{__name__}", "i")


# def create_data_model_from_views(
#     cdf_client: CogniteClient,
#     space: str,
#     data_model_external_id: str,
#     data_model_name: str,
#     data_model_description: str,
#     version: str,
#     views: list[data_modeling.ViewApply | data_modeling.ViewId],
# ) -> list[data_modeling.DataModelApply]:
#     """
#     Creates a data model from a list of views and publishes it to the specified space. This function constructs a
#     data model that includes the provided views and publishes the data model to CDF.

#     Args:
#         cdf_client (CogniteClient): The Cognite client.
#         space (str): The space identifier where the data model will reside.
#         data_model_external_id (str): The external ID for the data model.
#         data_model_name (str): The name of the data model.
#         data_model_description (str): A description of the data model.
#         version (str): The version identifier for the data model.
#         views (list[data_modeling.ViewApply | data_modeling.ViewId]): A list of views to be included in the data model,
#             which can be either ViewApply objects or ViewId references.

#     Returns:
#         list[data_modeling.DataModelApply]: A list containing the created DataModelApply objects.
#     """
#     new_data_model = [
#         data_modeling.DataModelApply(
#             space=space,
#             external_id=data_model_external_id,
#             name=data_model_name,
#             version=version,
#             description=data_model_description,
#             views=views,
#         )
#     ]
#     # TODO: implement Dry run
#     cdf_client.data_modeling.data_models.apply(new_data_model)
#     logging.info(f"Created data model {space, data_model_external_id}")
#     return new_data_model


# def upsert_data_model_from_gql(
#     cdf_client: CogniteClient,
#     space: str,
#     data_model_external_id: str,
#     data_model_name: str,
#     data_model_desc: str,
#     data_model_version: str,
#     gql_schema: str,
# ) -> dict:
#     """
#     Upserts a data model from a defined GraphQL schema using the DML API. This function uses the provided GraphQL schema to create or update a data model in the specified space.

#     Args:
#         cdf_client (CogniteClient): The Cognite client.
#         space (str): The space identifier where the data model will reside.
#         data_model_external_id (str): The external ID for the data model.
#         data_model_name (str): The name of the data model.
#         data_model_desc (str): A description of the data model.
#         data_model_version (str): The version identifier for the data model.
#         gql_schema (str): The GraphQL schema defining the data model.
#     Notes:
#         - This function sets up a GraphQL client with the appropriate configuration from the Cognite client.
#         - It constructs a GraphQL mutation query to upsert the data model using the provided schema and parameters.
#     Returns:
#         dict: The response from the GraphQL API after attempting to upsert the data model.
#     """
#     gql_client = setup_gql_client(
#         url=f"{cdf_client.config.base_url}/api/v1/projects/{cdf_client.config.project}/dml/graphql",
#         token=(cdf_client.config.credentials._refresh_access_token()[0]),
#         project_name=cdf_client.config.project,
#         cdf_cluster=cdf_client.config.base_url.split(".cognitedata.com")[0].replace("https://", ""),
#         header_aux=None,
#     )

#     upsert_query_str = """
#         mutation createUpdateDataModel($dmCreate: GraphQlDmlVersionUpsert!) {
#             upsertGraphQlDmlVersion(graphQlDmlVersion: $dmCreate) {
#               errors {
#                 kind
#                 message
#                 hint
#                 location {
#                   start {
#                     line
#                     column
#                   }
#                 }
#               }
#               result {
#                 space
#                 externalId
#                 version
#                 name
#                 description
#                 graphQlDml
#                 createdTime
#                 lastUpdatedTime
#               }
#             }
#         }
#     """
#     params = {
#         "dmCreate": {
#             "space": space,
#             "externalId": data_model_external_id,
#             "version": data_model_version,
#             "graphQlDml": gql_schema,
#             "name": data_model_name,
#             "description": data_model_desc,
#         }
#     }

#     response = execute_gql_query(upsert_query_str, params, gql_client)
#     logging.info(f"Upserted domain model '{data_model_external_id}' version '{data_model_version}' to space {space}")

#     return response


# def regenrate_DML(
#     cdf_client: CogniteClient,
#     space: str,
#     data_model_external_id: str,
#     version: str,
# ) -> str:
#     generated_DML = cdf_client.data_modeling.graphql._unsafely_wipe_and_regenerate_dml(
#         (space, data_model_external_id, version)
#     )
#     logging.info(f"DML regenerated for data model {space, data_model_external_id}")
#     return generated_DML
