from collections.abc import Callable
from typing import Any, Literal

import hypothesis.strategies as st

from cognite.neat._data_model.models.dms import (
    EnumProperty,
    PropertyTypeDefinition,
)
from cognite.neat._data_model.models.dms._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    INSTANCE_ID_PATTERN,
    SPACE_FORMAT_PATTERN,
)
from cognite.neat._utils.auxiliary import get_concrete_subclasses

AVAILABLE_PROPERTY_TYPES = [
    # Skipping enum as it requires special handling
    subclass.model_fields["type"].default
    for subclass in get_concrete_subclasses(PropertyTypeDefinition)
    if subclass is not EnumProperty
]


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
def reverse_direct_property(
    draw: Callable,
    connection_types: list[Literal["single_reverse_direct_relation", "multi_reverse_direct_relation"]] | None = None,
) -> dict[str, Any]:
    connection_types = connection_types or ["single_reverse_direct_relation", "multi_reverse_direct_relation"]
    return dict(
        connectionType=draw(st.sampled_from(connection_types)),
        name=draw(st.text(max_size=255)),
        description=draw(st.text(max_size=1024)),
        source=draw(view_reference()),
        through=draw(container_direct_reference()),
        targetsList=draw(st.booleans()),
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
            min_size=4,
            max_size=6,
            unique=True,
        )
    )
    # Ensure we get one of each property type
    properties = {
        prop_keys[0]: draw(edge_property()),
        prop_keys[1]: draw(reverse_direct_property(connection_types=["single_reverse_direct_relation"])),
        prop_keys[2]: draw(reverse_direct_property(connection_types=["multi_reverse_direct_relation"])),
        prop_keys[3]: draw(primary_property()),
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


@st.composite
def data_model_strategy(draw: Callable) -> dict[str, Any]:
    view_list = draw(st.lists(view_reference(), min_size=1, max_size=10, unique_by=lambda v: v["externalId"]))
    return dict(
        space=draw(st.from_regex(SPACE_FORMAT_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 43)),
        externalId=draw(st.from_regex(DM_EXTERNAL_ID_PATTERN, fullmatch=True).filter(lambda s: 1 <= len(s) <= 255)),
        version=draw(st.from_regex(DM_VERSION_PATTERN, fullmatch=True).filter(lambda s: len(s) <= 43)),
        name=draw(st.one_of(st.none(), st.text(max_size=255))),
        description=draw(st.one_of(st.none(), st.text(max_size=1024))),
        views=view_list,
        createdTime=draw(st.integers(min_value=0)),
        lastUpdatedTime=draw(st.integers(min_value=0)),
        isGlobal=draw(st.booleans()),
    )
