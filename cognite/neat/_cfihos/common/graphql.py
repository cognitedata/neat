# from gql import Client as gqlClient
# from gql import gql
# from gql.transport.requests import RequestsHTTPTransport


# def setup_gql_client(url: str, token: str, project_name: str, cdf_cluster: str, header_aux: dict) -> gqlClient:
#     """Sets up and returns the GQL client based on the received input

#     Args:
#         url (str): graphQL client endpoint
#         token (str): graphql token
#         project_name (str): name of cdf project
#         cdf_cluster (str): cluster cdf project is running on
#         header_aux (dict): Additional header elements
#     Returns:
#         gqlClient: the connected graphQL Client
#     """
#     try:
#         headers = {
#             "authorization": "Bearer " + token,  # your Access token
#             "project": project_name,
#             "cluster": cdf_cluster,
#         }
#         if header_aux:
#             for key, val in header_aux.items():
#                 headers[key] = val

#         transport = RequestsHTTPTransport(
#             url=url,
#             headers={
#                 "authorization": "Bearer " + token,  # your Access token
#                 "project": project_name,
#                 "cluster": cdf_cluster,
#             },
#             use_json=True,
#         )

#         gql_client = gqlClient(transport=transport, fetch_schema_from_transport=False)

#     except Exception as exc:
#         print(f"Failed to connect to gql clinet - {exc}")
#         raise

#     return gql_client


# def execute_gql_query(query: str, variables: dict, client: gqlClient) -> dict:
#     """Executes the provided graphQL query and returns the result

#     Args:
#         query (str): graphQL query that will be executed
#         variables (dict): variables that will be used in the query
#         client (gqlClient): the connect gqlClient

#     Returns:
#         dict: dictionary with the query response
#     """
#     try:
#         gql_query = gql(query)
#         result = client.execute(gql_query, variable_values=variables)
#         if result.get("error"):
#             raise Exception(f"Failed to execute query: {result.get('error')}")
#     except Exception as exc:
#         print(f"Failed to query data with gql - {exc}")
#         raise

#     return result
