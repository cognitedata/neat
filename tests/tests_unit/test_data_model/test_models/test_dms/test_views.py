from collections.abc import Callable, Iterator
from typing import Any, get_args

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from cognite.neat._data_model.models.dms import (
    EnumProperty,
    PropertyTypeDefinition,
    ViewPropertyDefinition,
    ViewRequest,
    ViewRequestProperty,
    ViewResponse,
    ViewResponseProperty,
)
from cognite.neat._data_model.models.dms._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    INSTANCE_ID_PATTERN,
    SPACE_FORMAT_PATTERN,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import humanize_validation_error

AVAILABLE_PROPERTY_TYPES = [
    # Skipping enum as it requires special handling
    subclass.model_fields["type"].default
    for subclass in get_concrete_subclasses(PropertyTypeDefinition)
    if subclass is not EnumProperty
]


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
            "Missing required field: 'space'",
            "In field name string should have at most 255 characters",
            "In field version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'",
            "In implements[1] missing required field: 'version'",
            "In implements[1].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'",
            "In properties.containerProp.primary_property.containerPropertyIdentifier "
            "string should match pattern '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'",
            "In properties.edgeProp.single_edge_connection.direction input should be "
            "'outwards' or 'inwards'. Got 'sideways'.",
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
            "In field description string should have at most 1024 characters",
            "In field externalId 'Query' is a reserved view External ID. Reserved External IDs are: Boolean, "
            "Date, File, Float, Float32, Float64, Int, Int32, Int64, JSONObject, Mutation, Numeric, PageInfo, Query, "
            "Sequence, String, Subscription, TimeSeries and Timestamp",
            "In field properties 'space' is a reserved property identifier. Reserved identifiers are: createdTime, "
            "deletedTime, edge_id, extensions, externalId, lastUpdatedTime, node_id, project_id, property_group, "
            "seq, space and tg_table_name; Property 'invalidProp#' does not match the "
            "required pattern: ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$",
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
            "In field space string should have at least 1 character",
            "In field externalId string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'",
            "In field version string should have at most 43 characters",
            "In properties.multiEdge.multi_edge_connection.source missing required field: 'version'",
            "In properties.reverseDirect.single_reverse_direct_relation.through.identifier "
            "string should have at least 1 character",
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
            "In implements[1] missing required field: 'version'",
            "In implements[2].space string should match pattern '^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$'",
            "In implements[2].externalId string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'",
            "In implements[2].version string should match pattern '^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'",
            "In properties.edgeProp.single_edge_connection.source.space string should have at least 1 character",
            "In properties.edgeProp.single_edge_connection.source.externalId string should have at least 1 character",
            "In properties.edgeProp.single_edge_connection.source.version string should match pattern "
            "'^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'",
            "In properties.edgeProp.single_edge_connection.type.externalId string should have at least 1 character",
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
            "In properties.containerProp.primary_property.container missing required field: 'externalId'",
            "In properties.containerProp.primary_property.containerPropertyIdentifier string should match pattern "
            "'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'",
            "In properties.containerProp.primary_property.name string should have at most 255 characters",
            "In properties.containerProp.primary_property.description string should have at most 1024 characters",
            "In properties.multiReverseDirect.multi_reverse_direct_relation.source.version string should match pattern "
            "'^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$'",
            "In properties.multiReverseDirect.multi_reverse_direct_relation.through.identifier string "
            "should match pattern '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$'",
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
            "In field externalId string should match pattern '^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$'",
            "In field properties 'externalId' is a reserved property identifier. Reserved identifiers are: "
            "createdTime, deletedTime, edge_id, extensions, externalId, lastUpdatedTime, node_id, project_id, "
            "property_group, seq, space and tg_table_name",
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
            "In properties.invalidContainer.primary_property.container.externalId "
            "string should have at least 1 character",
            "In properties.invalidEdge.single_edge_connection.type.space string should have at least 1 character",
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


@st.composite
def view_reference(draw: Callable) -> dict[str, Any]:
    return {
        "space": draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        "externalId": draw(st.from_regex(DM_EXTERNAL_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 255)),
        "version": draw(st.from_regex(DM_EXTERNAL_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
    }


@st.composite
def container_reference(draw: Callable) -> dict[str, Any]:
    return {
        "space": draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        "externalId": draw(st.from_regex(DM_EXTERNAL_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 255)),
    }


@st.composite
def node_reference(draw: Callable) -> dict[str, Any]:
    return {
        "space": draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        "externalId": draw(st.from_regex(INSTANCE_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 255)),
    }


@st.composite
def container_direct_reference(draw: Callable) -> dict[str, Any]:
    return {
        "source": draw(container_reference()),
        "identifier": draw(st.from_regex(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN, fullmatch=True)),
    }


@st.composite
def edge_property(draw: Callable) -> dict[str, Any]:
    return dict(
        connectionType=draw(st.sampled_from(["single_edge_connection", "multi_edge_connection"])),
        name=draw(st.text(max_size=255)),
        description=draw(st.text(max_size=1024)),
        source=draw(view_reference()),
        type=draw(node_reference()),
        edgeSource=draw(st.one_of(st.none(), view_reference())),
        direction=draw(st.sampled_from(["outwards", "inwards"])),
    )


@st.composite
def reverse_direct_property(draw: Callable) -> dict[str, Any]:
    return dict(
        connectionType=draw(st.sampled_from(["single_reverse_direct_relation", "multi_reverse_direct_relation"])),
        name=draw(st.text(max_size=255)),
        description=draw(st.text(max_size=1024)),
        source=draw(view_reference()),
        through=draw(container_direct_reference()),
    )


@st.composite
def primary_property(draw: Callable) -> dict[str, Any]:
    return dict(
        connectionType="primary_property",
        name=draw(st.one_of(st.none(), st.text(max_size=255))),
        description=draw(st.one_of(st.none(), st.text(max_size=1024))),
        container=draw(container_reference()),
        containerPropertyIdentifier=draw(
            st.from_regex(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN, fullmatch=True)
        ),
        source=draw(st.one_of(st.none(), view_reference())),
        immutable=draw(st.one_of(st.none(), st.booleans())),
        nullable=draw(st.one_of(st.none(), st.booleans())),
        autoIncrement=draw(st.one_of(st.none(), st.booleans())),
        defaultValue=draw(st.one_of(st.none(), st.text(), st.integers())),
        type={"type": draw(st.sampled_from(AVAILABLE_PROPERTY_TYPES))},
        constraintState={"nullability": draw(st.sampled_from(["current", "pending", "failed"]))},
    )


@st.composite
def view_strategy(draw: Callable) -> dict[str, Any]:
    # Generate property keys matching the pattern
    prop_keys = draw(
        st.lists(
            st.from_regex(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN, fullmatch=True),
            min_size=3,
            max_size=6,
            unique=True,
        )
    )
    # Ensure we get one of each property type
    properties = {
        prop_keys[0]: draw(edge_property()),
        prop_keys[1]: draw(reverse_direct_property()),
        prop_keys[2]: draw(primary_property()),
    }
    for key in prop_keys[3:]:
        properties[key] = draw(st.one_of([edge_property(), reverse_direct_property(), primary_property()]))
    mapped_containers = [prop["container"] for prop in properties.values() if "container" in prop]
    return dict(
        space=draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        externalId=draw(st.from_regex(DM_EXTERNAL_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 255)),
        version=draw(st.from_regex(DM_VERSION_PATTERN, fullmatch=True).filter(lambda s: len(s) <= 43)),
        name=draw(st.one_of(st.none(), st.text(max_size=255))),
        description=draw(st.one_of(st.none(), st.text(max_size=1024))),
        usedFor=draw(st.sampled_from(["node", "edge", "all"])),
        properties=properties,
        isGlobal=draw(st.booleans()),
        createdTime=draw(st.integers(min_value=0)),
        lastUpdatedTime=draw(st.integers(min_value=0)),
        queryable=draw(st.booleans()),
        writable=draw(st.booleans()),
        mappedContainers=mapped_containers,
    )


class TestViewResponse:
    @settings(max_examples=1)
    @given(view_strategy())
    def test_as_request(self, view: dict[str, Any]) -> None:
        response = ViewResponse.model_validate(view)

        assert isinstance(response, ViewResponse)

        request = response.as_request()
        assert isinstance(request, ViewRequest)

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
            assert dumped_prop == response_dumped_prop
