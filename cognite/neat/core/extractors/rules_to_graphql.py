import logging
import re
import warnings

import pandas as pd
from graphql import GraphQLError, GraphQLField, GraphQLList, GraphQLNonNull, GraphQLObjectType, GraphQLSchema
from graphql import assert_name as assert_graphql_name
from graphql import print_schema

from cognite.neat.core.data_classes.transformation_rules import DATA_TYPE_MAPPING, TransformationRules


def get_invalid_names(entity_names: set) -> set:
    """Returns a set of invalid entity names"""
    invalid_names = set()
    for entity_name in entity_names:
        try:
            assert_graphql_name(entity_name)
        except GraphQLError:
            invalid_names.add(entity_name)
    return invalid_names


def repair_name(name: str, entity_type: str, fix_casing: bool = False) -> str:
    """Repairs an entity name to conform to GraphQL naming convention"""

    # Remove any non GraphQL compliant characters
    repaired_string = re.sub(r"[^_a-zA-Z0-9/_]", "", name)

    # Name must start with a letter or underscore
    if repaired_string[0].isdigit():
        repaired_string = f"_{repaired_string}"

    if not fix_casing:
        return repaired_string
    # Property names must be camelCase
    if entity_type == "property" and repaired_string[0].isupper():
        return repaired_string[0].lower() + repaired_string[1:]
    # Class names must be PascalCase
    elif entity_type == "class" and repaired_string[0].islower():
        return repaired_string[0].upper() + repaired_string[1:]
    else:
        return repaired_string


def _remove_query_type(schema_string: str) -> str:
    """Removes unnecessary Query type to conform to Cognite's GraphQL API"""
    lines = schema_string.split("\n")

    for _i, line in enumerate(lines):
        if "}" in line:
            break

    return "\n".join(lines[_i + 2 :])


def _get_graphql_schema_string(schema: GraphQLSchema) -> str:
    return _remove_query_type(print_schema(schema))


def rules2graphql_schema(
    transformation_rules: TransformationRules, fix_names: bool = True, fix_casing: bool = False
) -> str:
    """Generates a GraphQL schema from an instance of TransformationRules

    Parameters
    ----------
    transformation_rules : TransformationRules
        TransformationRules object
    fix_names : bool, optional
        Whether to attempt to repair invalid entity names, by default True
    fix_casing : bool, optional
        Whether to attempt to fix casing of entity names, by default False

    Returns
    -------
    str
        GraphQL schema string
    """
    gql_type_definitions: dict = {}
    invalid_names: set = get_invalid_names(transformation_rules.get_entity_names())

    if invalid_names and not fix_names:
        msg = "Entity names must only contain [_a-zA-Z0-9] characters and can start only with [_a-zA-Z]"
        logging.error(f"{msg}, following entities {invalid_names} do not follow these rules!")
        raise GraphQLError(f"{msg}, following entities {invalid_names} do not follow these rules!")
    elif invalid_names and fix_names:
        msg = "Entity names must only contain [_a-zA-Z0-9] characters and can start only with [_a-zA-Z]"
        logging.warn(
            f"{msg}, following entities {invalid_names} do not follow these rules! Attempting to repair names..."
        )
        warnings.warn(
            f"{msg}, following entities {invalid_names} do not follow these rules! Attempting to repair names...",
            stacklevel=2,
        )

    def _define_fields(property_definitions: pd.DataFrame) -> dict[str, GraphQLField]:
        gql_field_definitions = {}
        for property_, row in property_definitions.iterrows():
            property_name = repair_name(property_, "property", fix_casing=fix_casing)  # type: ignore
            # Node attribute
            if row.property_type == "DatatypeProperty":
                value_type_gql = DATA_TYPE_MAPPING[row.value_type]["GraphQL"]

                # Case: Mandatory, single value
                if row.min_count and row.max_count == 1:
                    gql_field_definitions[property_name] = GraphQLField(GraphQLNonNull(value_type_gql))

                # Case: Mandatory, multiple value
                elif row.min_count and row.max_count != 1:
                    gql_field_definitions[property_name] = GraphQLField(
                        GraphQLNonNull(GraphQLList(GraphQLNonNull(value_type_gql)))
                    )

                # Case: Optional, single value
                elif row.max_count == 1:
                    gql_field_definitions[property_name] = GraphQLField(value_type_gql)

                # Case: Optional, multiple value
                else:
                    gql_field_definitions[property_name] = GraphQLField(GraphQLList(value_type_gql))

            # Node edge
            else:
                # Case: one to one edge
                if row.min_count and row.max_count == 1:
                    gql_field_definitions[property_name] = GraphQLField(
                        gql_type_definitions[repair_name(row.value_type, "class", fix_casing=fix_casing)]
                    )

                # Case: one to many edge
                else:
                    gql_field_definitions[property_name] = GraphQLField(
                        GraphQLList(gql_type_definitions[repair_name(row.value_type, "class", fix_casing=fix_casing)])
                    )

        return gql_field_definitions

    for class_, properties in transformation_rules.to_dataframe().items():
        gql_type_definitions[repair_name(class_, "class", fix_casing=fix_casing)] = GraphQLObjectType(
            repair_name(class_, "class", fix_casing=fix_casing),
            lambda properties=properties: _define_fields(properties),
        )

    # Needs this so we are able to generate the schema string
    query_schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query", lambda: {type_name: GraphQLField(type_def) for type_name, type_def in gql_type_definitions.items()}
        )
    )
    return _get_graphql_schema_string(query_schema)
