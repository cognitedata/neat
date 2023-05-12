import pandas as pd
from graphql import GraphQLField, GraphQLList, GraphQLNonNull, GraphQLObjectType, GraphQLSchema, print_schema

from cognite.neat.core.data_classes.transformation_rules import DATA_TYPE_MAPPING, TransformationRules


def _remove_query_type(schema_string: str) -> str:
    """Removes unnecessary Query type to conform to Cognite's GraphQL API"""
    lines = schema_string.split("\n")

    for _i, line in enumerate(lines):
        if "}" in line:
            break

    return "\n".join(lines[_i + 2 :])


def _get_graphql_schema_string(schema: GraphQLSchema) -> str:
    return _remove_query_type(print_schema(schema))


def rules2graphql(transformation_rules: TransformationRules) -> str:
    """Generates a GraphQL schema from an instance of TransformationRules

    Parameters
    ----------
    transformation_rules : TransformationRules
        TransformationRules object

    Returns
    -------
    str
        GraphQL schema string
    """
    schema = {}

    def _define_fields(property_definitions: pd.DataFrame) -> dict[str, GraphQLField]:
        gql_type_definitions = {}
        for property_, row in property_definitions.iterrows():
            # Node attribute
            if row.property_type == "DatatypeProperty":
                value_type_gql = DATA_TYPE_MAPPING[row.value_type]["GraphQL"]

                # Case: Mandatory, single value
                if row.min_count and row.max_count == 1:
                    gql_type_definitions[property_] = GraphQLField(GraphQLNonNull(value_type_gql))

                # Case: Mandatory, multiple value
                elif row.min_count and row.max_count != 1:
                    gql_type_definitions[property_] = GraphQLField(
                        GraphQLNonNull(GraphQLList(GraphQLNonNull(value_type_gql)))
                    )

                # Case: Optional, single value
                elif row.max_count == 1:
                    gql_type_definitions[property_] = GraphQLField(value_type_gql)

                # Case: Optional, multiple value
                else:
                    gql_type_definitions[property_] = GraphQLField(GraphQLList(value_type_gql))

            # Node links
            else:
                # Case: one to one link
                if row.min_count and row.max_count == 1:
                    gql_type_definitions[property_] = GraphQLField(schema[row.value_type])

                # Case: one to many links
                else:
                    gql_type_definitions[property_] = GraphQLField(GraphQLList(schema[row.value_type]))

        return gql_type_definitions

    for class_, properties in transformation_rules.to_dataframe().items():
        schema[class_] = GraphQLObjectType(class_, lambda properties=properties: _define_fields(properties))

    # Needs this so we are able to generate the schema string
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query", lambda: {type_name: GraphQLField(type_def) for type_name, type_def in schema.items()}
        )
    )
    return _get_graphql_schema_string(schema)
