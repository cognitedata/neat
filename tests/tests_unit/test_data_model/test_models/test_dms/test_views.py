from collections.abc import Iterator
from typing import Any, get_args

import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import (
    ViewPropertyDefinition,
    ViewReference,
    ViewRequest,
    ViewRequestProperty,
    ViewResponse,
    ViewResponseProperty,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error

from .strategies import view_strategy


def test_all_view_properties_are_in_union() -> None:
    all_property_classes = get_concrete_subclasses(ViewPropertyDefinition, exclude_direct_abc_inheritance=True)
    response_union = get_args(ViewResponseProperty.__args__[0])
    request_union = get_args(ViewRequestProperty.__args__[0])
    all_properties_union = set(response_union).union(set(request_union))
    missing = set(all_property_classes) - set(all_properties_union)
    assert not missing, (
        f"The following ViewPropertyDefinitions subclasses are "
        f"missing from the ViewPropertyDefinitions union: {humanize_collection([cls.__name__ for cls in missing])}"
    )


def invalid_view_definition_test_cases() -> Iterator[tuple]:
    yield pytest.param(
        {
            "externalId": "MyView",
            "name": "way too long name" * 100,
            "version": "#NotValid",
            "implements": [{"space": "*my_invalid_space", "externalId": "MyParent"}],
            "properties": {
                "containerProp": {
                    "container": {"space": "my_space", "externalId": "MyContainer"},
                    "containerPropertyIdentifier": "invalid#name",
                },
                "edgeProp": {
                    "connectionType": "single_edge_connection",
                    "source": {"space": "my_space", "externalId": "MySourceView", "version": "1"},
                    "type": {"space": "my_space", "externalId": "MyNode"},
                    "direction": "sideways",
                },
            },
        },
        {
            "In field 'name', string should have at most 255 characters.",
            "In field 'version', string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In implements[1] missing required field: 'version'.",
            "In implements[1].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'.",
            "In properties.containerProp.primary_property.containerPropertyIdentifier "
            "string should match pattern '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'.",
            "In properties.edgeProp.single_edge_connection.direction input should be "
            "'outwards' or 'inwards'. Got 'sideways'.",
            "Missing required field: 'space'.",
        },
        id="Multiple Issues.",
    )

    yield pytest.param(
        {
            "space": "String",
            "externalId": "Query",
            "version": "1",
            "description": "x" * 1025,
            "properties": {
                "space": {
                    "container": {"space": "my_space", "externalId": "MyContainer"},
                    "containerPropertyIdentifier": "validProp",
                },
                "invalidProp#": {
                    "container": {"space": "my_space", "externalId": "MyContainer"},
                    "containerPropertyIdentifier": "validProp",
                },
            },
        },
        {
            "In field 'description', string should have at most 1024 characters.",
            "In field 'externalId', 'Query' is a reserved view External ID. Reserved "
            "External IDs are: Boolean, Date, File, Float, Float32, Float64, Int, Int32, "
            "Int64, JSONObject, Mutation, Numeric, PageInfo, Query, Sequence, String, "
            "Subscription, TimeSeries and Timestamp.",
            "In field 'properties', 'space' is a reserved property identifier. Reserved "
            "identifiers are: createdTime, deletedTime, edge_id, extensions, externalId, "
            "lastUpdatedTime, node_id, project_id, property_group, seq, space and "
            "tg_table_name; Property 'invalidProp#' does not match the required pattern: "
            "^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$.",
        },
        id="Forbidden values and reserved identifiers.",
    )

    yield pytest.param(
        {
            "space": "",
            "externalId": "123invalid",
            "version": "x" * 44,
            "name": "",
            "properties": {
                "multiEdge": {
                    "connectionType": "multi_edge_connection",
                    "source": {"space": "short", "externalId": "View"},
                    "type": {"space": "my_space", "externalId": "Node"},
                    "direction": "outwards",
                },
                "reverseDirect": {
                    "connectionType": "single_reverse_direct_relation",
                    "source": {"space": "my_space", "externalId": "View", "version": "1"},
                    "through": {"source": {"space": "invalid-", "externalId": "Container"}, "identifier": ""},
                },
            },
        },
        {
            "In field 'externalId', string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'.",
            "In field 'space', string should have at least 1 character.",
            "In field 'version', string should have at most 43 characters.",
            "In properties.multiEdge.multi_edge_connection.source missing required field: 'version'.",
            "In "
            "properties.reverseDirect.single_reverse_direct_relation.through.ContainerDirectReference.identifier "
            "string should have at least 1 character.",
            "In "
            "properties.reverseDirect.single_reverse_direct_relation.through.ViewDirectReference.identifier "
            "string should have at least 1 character.",
            "In "
            "properties.reverseDirect.single_reverse_direct_relation.through.ViewDirectReference.source "
            "missing required field: 'version'.",
        },
        id="Field length and pattern violations.",
    )

    yield pytest.param(
        {
            "space": "my_space",
            "externalId": "MyView",
            "version": "1",
            "implements": [
                {"space": "space1", "externalId": "View1"},
                {"space": "123invalid", "externalId": "9invalid", "version": ".invalid"},
            ],
            "properties": {
                "edgeProp": {
                    "connectionType": "single_edge_connection",
                    "source": {"space": "", "externalId": "", "version": ""},
                    "type": {"space": "node_space", "externalId": ""},
                    "edgeSource": {"space": "edge_space", "externalId": "EdgeView", "version": "1"},
                    "direction": "inwards",
                },
            },
        },
        {
            "In implements[1] missing required field: 'version'.",
            "In implements[2].externalId string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'.",
            "In implements[2].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'.",
            "In implements[2].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In properties.edgeProp.single_edge_connection.source.externalId string should have at least 1 character.",
            "In properties.edgeProp.single_edge_connection.source.space string should have at least 1 character.",
            "In properties.edgeProp.single_edge_connection.source.version string should "
            "match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In properties.edgeProp.single_edge_connection.type.externalId string should have at least 1 character.",
        },
        id="Empty fields and invalid implements.",
    )

    yield pytest.param(
        {
            "space": "my_space",
            "externalId": "MyView",
            "version": "1",
            "properties": {
                "containerProp": {
                    "container": {"space": "container_space"},
                    "containerPropertyIdentifier": "_invalid",
                    "name": "x" * 256,
                    "description": "x" * 1025,
                },
                "multiReverseDirect": {
                    "connectionType": "multi_reverse_direct_relation",
                    "source": {"space": "source_space", "externalId": "SourceView", "version": "invalid_version#"},
                    "through": {
                        "source": {"space": "through_space", "externalId": "ThroughContainer"},
                        "identifier": "invalid#identifier",
                    },
                },
            },
        },
        {
            "In properties.containerProp.primary_property.container missing required field: 'externalId'.",
            "In properties.containerProp.primary_property.containerPropertyIdentifier "
            "string should match pattern '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'.",
            "In properties.containerProp.primary_property.description string should have at most 1024 characters.",
            "In properties.containerProp.primary_property.name string should have at most 255 characters.",
            "In "
            "properties.multiReverseDirect.multi_reverse_direct_relation.source.version "
            "string should match pattern "
            "'^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'.",
            "In "
            "properties.multiReverseDirect.multi_reverse_direct_relation.through.ContainerDirectReference.identifier "
            "string should match pattern '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'.",
            "In "
            "properties.multiReverseDirect.multi_reverse_direct_relation.through.ViewDirectReference.identifier "
            "string should match pattern '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'.",
            "In "
            "properties.multiReverseDirect.multi_reverse_direct_relation.through.ViewDirectReference.source "
            "missing required field: 'version'.",
        },
        id="Property validation errors.",
    )

    yield pytest.param(
        {
            "space": "my-space",
            "externalId": "MyView_",
            "version": "1",
            "properties": {
                "edgeSource": {
                    "connectionType": "single_edge_connection",
                    "source": {"space": "v", "externalId": "V", "version": "v"},
                    "type": {"space": "n", "externalId": "N"},
                    "direction": "inwards",
                },
                "externalId": {
                    "container": {"space": "my_space", "externalId": "MyContainer"},
                    "containerPropertyIdentifier": "prop",
                },
            },
        },
        {
            "In field 'externalId', string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'.",
            "In field 'properties', 'externalId' is a reserved property identifier. "
            "Reserved identifiers are: createdTime, deletedTime, edge_id, extensions, "
            "externalId, lastUpdatedTime, node_id, project_id, property_group, seq, space "
            "and tg_table_name.",
        },
        id="Single reserved property identifier.",
    )

    yield pytest.param(
        {
            "space": "Boolean",
            "externalId": "MyView",
            "version": "v1.0.1",
            "properties": {
                "invalidContainer": {
                    "container": {"space": "s", "externalId": ""},
                    "containerPropertyIdentifier": "prop",
                },
                "invalidEdge": {
                    "connectionType": "single_edge_connection",
                    "source": {"space": "s", "externalId": "V", "version": "1"},
                    "type": {"space": "", "externalId": "N"},
                    "direction": "outwards",
                },
            },
        },
        {
            "In properties.invalidContainer.primary_property.container.externalId string "
            "should have at least 1 character.",
            "In properties.invalidEdge.single_edge_connection.type.space string should have at least 1 character.",
        },
        id="Empty reference fields.",
    )


class TestViewRequests:
    @pytest.mark.parametrize("data,expected_errors", list(invalid_view_definition_test_cases()))
    def test_invalid_definitions(self, data: dict[str, Any], expected_errors: set[str]) -> None:
        with pytest.raises(ValidationError) as excinfo:
            ViewRequest.model_validate(data)
        errors = set(humanize_validation_error(excinfo.value))
        assert errors == expected_errors


class TestViewResponse:
    @settings(max_examples=1)
    @given(view_strategy())
    def test_as_request(self, view: dict[str, Any]) -> None:
        response = ViewResponse.model_validate(view)

        assert isinstance(response, ViewResponse)

        request = response.as_request()
        assert isinstance(request, ViewRequest)

        reference = response.as_reference()
        assert isinstance(reference, ViewReference)

        # Properties have differences in request and response, so we need to compare them
        # separately
        dumped = request.model_dump(exclude={"properties"})
        response_dumped = response.model_dump(exclude={"properties"})
        response_only_keys = set(ViewResponse.model_fields.keys()) - set(ViewRequest.model_fields.keys())
        for keys in response_only_keys:
            response_dumped.pop(keys, None)
        assert dumped == response_dumped

        assert list(request.properties.keys()) == list(response.properties.keys())
        for request_prop, response_prop in zip(request.properties.values(), response.properties.values(), strict=False):
            dumped_prop = request_prop.model_dump()
            response_dumped_prop = response_prop.model_dump()
            response_only_prop_keys = set(type(response_prop).model_fields.keys()) - set(
                type(request_prop).model_fields.keys()
            )
            for keys in response_only_prop_keys:
                response_dumped_prop.pop(keys, None)
            request_only_prop_keys = set(type(request_prop).model_fields.keys()) - set(
                type(response_prop).model_fields.keys()
            )
            for keys in request_only_prop_keys:
                dumped_prop.pop(keys, None)
            assert dumped_prop == response_dumped_prop
