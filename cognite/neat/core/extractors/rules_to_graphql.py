import logging
import re
import warnings

from graphql import GraphQLError, GraphQLField, GraphQLList, GraphQLNonNull, GraphQLObjectType, GraphQLSchema
from graphql import assert_name as assert_graphql_name
from graphql import print_schema

from cognite.neat.core.data_classes.transformation_rules import DATA_TYPE_MAPPING, Property, TransformationRules


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
    """
    Repairs an entity name to conform to GraphQL naming convention
    >>> repair_name("wind-speed", "property")
    'windspeed'
    >>> repair_name("Wind.Speed", "property", True)
    'windSpeed'
    >>> repair_name("windSpeed", "class", True)
    'WindSpeed'
    >>> repair_name("22windSpeed", "class")
    '_22windSpeed'
    """

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
    """Removes unnecessary Query types to conform to Cognite's GraphQL API"""
    lines = schema_string.split("\n")

    for _i, line in enumerate(lines):
        if "}" in line:
            break

    return "\n".join(lines[_i + 2 :])


def _get_graphql_schema_string(schema: GraphQLSchema) -> str:
    return _remove_query_type(print_schema(schema))


def rules2graphql_schema(
    transformation_rules: TransformationRules,
    stop_on_exception: bool = False,
    fix_casing: bool = False,
) -> str:
    """Generates a GraphQL schema from an instance of TransformationRules

    Parameters
    ----------
    transformation_rules : TransformationRules
        TransformationRules object
    stop_on_exception : bool, optional
        Stop on any exception, by default False
    fix_casing : bool, optional
        Whether to attempt to fix casing of entity names, by default False

    Returns
    -------
    str
        GraphQL schema string
    """
    gql_type_definitions: dict = {}
    invalid_names: set = get_invalid_names(transformation_rules.get_entity_names())
    data_model_issues: set = transformation_rules.check_data_model_definitions()

    if invalid_names and stop_on_exception:
        msg = "Entity names must only contain [_a-zA-Z0-9] characters and can start only with [_a-zA-Z]"
        logging.error(f"{msg}, following entities {invalid_names} do not follow these rules!")
        raise GraphQLError(f"{msg}, following entities {invalid_names} do not follow these rules!")
    elif invalid_names and not stop_on_exception:
        msg = "Entity names must only contain [_a-zA-Z0-9] characters and can start only with [_a-zA-Z]"
        logging.warn(
            f"{msg}, following entities {invalid_names} do not follow these rules! Attempting to repair names..."
        )
        warnings.warn(
            f"{msg}, following entities {invalid_names} do not follow these rules! Attempting to repair names...",
            stacklevel=2,
        )

    if data_model_issues and stop_on_exception:
        msg = " ".join(data_model_issues)
        logging.error(msg)
        raise ValueError(msg)
    elif data_model_issues and not stop_on_exception:
        msg = " ".join(data_model_issues)
        msg += " Redefinitions will be skipped!"
        logging.warn(msg)
        warnings.warn(
            msg,
            stacklevel=2,
        )

    def _define_fields(property_definitions: list[Property]) -> dict[str, GraphQLField]:
        gql_field_definitions = {}
        for property_ in property_definitions:
            property_name = repair_name(property_.property_name, "property", fix_casing=fix_casing)  # type: ignore

            if property_name in gql_field_definitions:
                logging.warn(f"Property {property_name} being redefined... skipping!")
                warnings.warn(f"Property {property_name} being redefined... skipping!", stacklevel=2)
                continue

            # Node attribute
            if property_.property_type == "DatatypeProperty":
                value_type_gql = DATA_TYPE_MAPPING[property_.expected_value_type]["GraphQL"]

                # Case: Mandatory, single value
                if property_.min_count and property_.max_count == 1:
                    value = GraphQLNonNull(value_type_gql)
                # Case: Mandatory, multiple value
                elif property_.min_count and property_.max_count != 1:
                    value = GraphQLNonNull(GraphQLList(GraphQLNonNull(value_type_gql)))
                # Case: Optional, single value
                elif property_.max_count == 1:
                    value = value_type_gql
                # Case: Optional, multiple value
                else:
                    value = GraphQLList(value_type_gql)

                gql_field_definitions[property_name] = GraphQLField(value)

            # Node edge
            else:
                value = gql_type_definitions[repair_name(property_.expected_value_type, "class", fix_casing=fix_casing)]
                is_one_to_many_edge = not (property_.min_count and property_.max_count == 1)
                if is_one_to_many_edge:
                    value = GraphQLList(value)
                gql_field_definitions[property_name] = GraphQLField(value)

        return gql_field_definitions

    for class_, properties in transformation_rules.get_classes_with_properties().items():
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
