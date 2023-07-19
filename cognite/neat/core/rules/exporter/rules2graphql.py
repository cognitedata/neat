import logging
import re
import warnings

from graphql import GraphQLField, GraphQLList, GraphQLNonNull, GraphQLObjectType, GraphQLSchema, print_schema

from cognite.neat.core.rules import _exceptions
from cognite.neat.core.rules.analysis import (
    are_entity_names_dms_compliant,
    are_properties_redefined,
    get_classes_with_properties,
)
from cognite.neat.core.rules.models import DATA_TYPE_MAPPING, Property, TransformationRules
from cognite.neat.core.utils.utils import generate_exception_report


def _make_ids_compliant(transformation_rules: TransformationRules) -> TransformationRules:
    return transformation_rules


def rules2graphql_schema(
    transformation_rules: TransformationRules,
) -> str:
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
    names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
    properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)

    if not names_compliant:
        raise _exceptions.Error10(report=generate_exception_report(name_warnings))
    if properties_redefined:
        raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))

    def _define_fields(property_definitions: list[Property]) -> dict[str, GraphQLField]:
        gql_field_definitions = {}
        for property_ in property_definitions:
            # property_name = _repair_name(property_.property_name, "property", fix_casing=fix_casing)  # type: ignore

            property_name = property_.property_name

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

            # Node edge
            else:
                value = gql_type_definitions[property_.expected_value_type]
                is_one_to_many_edge = not (property_.min_count and property_.max_count == 1)
                if is_one_to_many_edge:
                    value = GraphQLList(value)
            gql_field_definitions[property_name] = GraphQLField(value)

        return gql_field_definitions

    gql_type_definitions: dict = {}
    for class_, properties in get_classes_with_properties(transformation_rules).items():
        gql_type_definitions[class_] = GraphQLObjectType(
            class_,
            lambda properties=properties: _define_fields(properties),
        )

    # Needs this so we are able to generate the schema string
    query_schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query", lambda: {type_name: GraphQLField(type_def) for type_name, type_def in gql_type_definitions.items()}
        )
    )
    return _get_graphql_schema_string(query_schema)


# def _get_invalid_names(entity_names: set) -> set:
#     """Returns a set of invalid entity names"""
#     return {entity_name for entity_name in entity_names if not re.match(name_compliance_regex, entity_name)}


def _repair_name(name: str, entity_type: str, fix_casing: bool = False) -> str:
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
    repaired_string = re.sub(r"[^_a-zA-Z0-9]", "", name)

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


def _get_graphql_schema_string(schema: GraphQLSchema) -> str:
    return _remove_query_type(print_schema(schema))


def _remove_query_type(schema_string: str) -> str:
    """Removes unnecessary Query types to conform to Cognite's GraphQL API"""
    lines = schema_string.split("\n")

    for _i, line in enumerate(lines):
        if "}" in line:
            break

    return "\n".join(lines[_i + 2 :])

    # invalid_names: set = _get_invalid_names(transformation_rules.get_entity_names())
    # data_model_issues: set = transformation_rules.check_data_model_definitions()

    # # this should be done when transformation rules are created
    # if invalid_names and stop_on_exception:
    #     msg = "Entity names must only contain [_a-zA-Z0-9] characters and can start only with [_a-zA-Z]"
    #     logging.error(f"{msg}, following entities {invalid_names} do not follow these rules!")
    #     raise GraphQLError(f"{msg}, following entities {invalid_names} do not follow these rules!")
    # elif invalid_names and not stop_on_exception:
    #     msg = "Entity names must only contain [_a-zA-Z0-9] characters and can start only with [_a-zA-Z]"
    #     logging.warn(
    #         f"{msg}, following entities {invalid_names} do not follow these rules! Attempting to repair names..."
    #     )
    #     warnings.warn(
    #         f"{msg}, following entities {invalid_names} do not follow these rules! Attempting to repair names...",
    #         stacklevel=2,
    #     )

    # if data_model_issues and stop_on_exception:
    #     msg = " ".join(data_model_issues)
    #     logging.error(msg)
    #     raise ValueError(msg)
    # elif data_model_issues and not stop_on_exception:
    #     msg = " ".join(data_model_issues)
    #     msg += " Redefinitions will be skipped!"
    #     logging.warn(msg)
    #     warnings.warn(
    #         msg,
    #         stacklevel=2,
    #     )
