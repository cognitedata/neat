from typing import Any, TypeVar, cast

import pandas as pd
from cognite.client.data_classes import Asset, Event, FileMetadata, Sequence, TimeSeries
from cognite.client.data_classes.data_modeling import Node

from cognite.neat._rules._constants import get_reserved_words

T_Classic = TypeVar("T_Classic", bound=Asset | TimeSeries | Event | Sequence | FileMetadata)


SERVER_SIDE = {"parentId", "id", "createdTime", "lastUpdatedTime", "rootId", "source", "dataSetId"}
NODE_SERVER_SIDE = {"version", "lastUpdatedTime", "createdTime", "instanceType", "path", "root", "pathLastUpdatedTime"}
RENAMING = {"parent": "parentExternalId"}
RESERVED_PROPERTIES = {word.replace("_", "").lower() for word in get_reserved_words("property")}


def as_classic(node: Node, classic: T_Classic) -> T_Classic:
    """Converts a Node to is corresponding Asset/TimeSeries/Event/Sequence/FileMetadata object.

    The use case for this function is to compare a migrated node with its source in the asset-centric schema in CDF.

    Args:
        node (Node): The node to convert.
        classic (T_Classic): The object to convert to.

    Returns:
        T_Classic: The converted object.
    """
    source = classic.dump()
    target = _flatten_node(node.dump())
    for key in NODE_SERVER_SIDE:
        target.pop(key, None)
    source_by_target = _create_renaming_dict(target, classic.metadata or {})
    target_by_source = {value: key for key, value in source_by_target.items()}
    data: dict[str, Any] = {}
    for source_key, source_value in source.items():
        if source_key in SERVER_SIDE:
            data[source_key] = source_value
            continue
        target_key = target_by_source.get(source_key, source_key)
        if target_key in target:
            data[source_key] = target[target_key]
    if classic.metadata:
        data["metadata"] = {}
        for source_key, source_value in classic.metadata.items():
            target_key = target_by_source.get(source_key, source_key)
            if target_key in target:
                if _are_equal_datetime(source_value, target[target_key]) or _are_equal_bool(
                    source_value, str(target[target_key])
                ):
                    data["metadata"][source_key] = source_value
                else:
                    data["metadata"][source_key] = str(target[target_key])
    return cast(T_Classic, type(classic)._load(data))


def _flatten_node(node: dict[str, Any]) -> dict[str, Any]:
    flat = {}
    for key, value in node.items():
        if isinstance(value, dict) and _is_direct_relation(value):
            flat[key] = value["externalId"]
        elif isinstance(value, dict):
            flat.update(_flatten_node(value))
        elif isinstance(value, list) and all(isinstance(item, dict) and _is_direct_relation(item) for item in value):
            flat[key] = [item["externalId"] for item in value]
        elif isinstance(value, list) and all(isinstance(item, dict) for item in value):
            flat[key] = [_flatten_node(item) for item in value]
        else:
            flat[key] = value
    return flat


def _is_direct_relation(value: dict) -> bool:
    return len(value) == 2 and {"space", "externalId"} == set(value)


def _create_renaming_dict(node: dict[str, Any], classic_metadata: dict[str, Any]) -> dict[str, str]:
    metadata_standard = {_lower_alpha(key): key for key in classic_metadata.keys()}
    node_standard = {_lower_alpha(key): key for key in node.keys()}
    node_standard = {
        key.removeprefix("my") if key.removeprefix("my") in RESERVED_PROPERTIES else key: value
        for key, value in node_standard.items()
    }
    return {
        **RENAMING,
        **{key: metadata_standard[std] for std, key in node_standard.items() if std in metadata_standard},
    }


def _are_equal_datetime(source: Any, target: Any) -> bool:
    if not isinstance(source, str) or not isinstance(target, str):
        return False
    source_time = pd.to_datetime(source, errors="coerce", utc=True)
    target_time = pd.to_datetime(target, errors="coerce")
    if source_time is pd.NaT or target_time is pd.NaT:
        return False
    return source_time == target_time


def _are_equal_bool(source: Any, target: Any) -> bool:
    if not isinstance(source, str) or not isinstance(target, str):
        return False
    return source.lower() in {"true", "false"} and target.lower() == source.lower()


def _lower_alpha(key: str) -> str:
    return "".join([c for c in key if c.isalpha()]).lower()
