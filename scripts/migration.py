"""This is a developer utils functions to compare the differences between the source and target objects.

It is not distributed with the package and is not intended for production use.
"""
import typing
from pprint import pprint
from typing import Any, TypeVar, cast

import pandas as pd
import pytest
from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, Event, FileMetadata, Sequence, TimeSeries
from cognite.client.data_classes.data_modeling import Node, ViewId

from cognite.neat.v0.core._data_model._constants import get_reserved_words

from deepdiff import DeepDiff

T_Classic = TypeVar("T_Classic", bound=Asset | TimeSeries | Event | Sequence | FileMetadata)


SERVER_SIDE = {"parentId", "id", "createdTime", "lastUpdatedTime", "rootId", "source", "dataSetId"}
NODE_SERVER_SIDE = {"version", "lastUpdatedTime", "createdTime", "instanceType", "path", "root", "pathLastUpdatedTime"}
RENAMING = {"parent": "parentExternalId"}
RESERVED_PROPERTIES = {word.replace("_", "").lower() for word in get_reserved_words("property")}


def display_diffs(
    source_items: typing.Sequence[Asset | TimeSeries | Event | Sequence | FileMetadata],
    target_view: ViewId | tuple[str, str, str],
    source: CogniteClient,
    target: CogniteClient | None = None,
) -> None:
    """Prints the differences between the source and target objects.

    Args:
        source_items (typing.Sequence[Asset | TimeSeries | Event | Sequence | FileMetadata]): The source objects.
        target_view (ViewId | tuple[str, str, str]): The target view.
        source (CogniteClient): The source client.
        target (CogniteClient, optional): The target client. Defaults to the source client

    Raises:
        NeatImportError: If the deepdiff package is not installed.

    """
    target_client = target or source
    dataset_by_id = {
        d.id: d.external_id
        for d in source.data_sets.retrieve_multiple(
            ids=list({item.data_set_id for item in source_items if item.data_set_id})
        )
    }
    target_instances = target_client.data_modeling.instances.retrieve(
        [
            (dataset_by_id[item.data_set_id].lower(), item.external_id)  # type: ignore[union-attr]
            for item in source_items
            if item.data_set_id and dataset_by_id.get(item.data_set_id) and item.external_id
        ],
        sources=target_view,
    )
    node_by_id = {node.external_id: node for node in target_instances.nodes}
    type_ = type(source_items[0]).__name__
    for item in source_items:
        if item.external_id not in node_by_id:
            print(f"{type_} {item.external_id} is missing")
            continue
        node = node_by_id[item.external_id]
        classic_node = as_classic(node, item)
        if classic_node != item:
            print(f"Failed: {type_} {item.external_id!r}")
            pprint(DeepDiff(item.dump(), classic_node.dump()))


def as_classic(node: Node, classic: T_Classic) -> T_Classic:
    """Converts a Node to its corresponding Asset/TimeSeries/Event/Sequence/FileMetadata object.

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
            elif source_value in {"nan", "null", "none", "", " ", "nil", "n/a", "na", "unknown", "undefined"}:
                # These are filtered out by neat.
                data["metadata"][source_key] = source_value
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


@pytest.fixture()
def migrated_asset() -> tuple[dict[str, Any], dict[str, Any]]:
    asset = {
        "externalId": "Asset 105876",
        "name": "347",
        "parentId": 1331482884473656,
        "parentExternalId": "Asset 12966",
        "description": "Lube oil system",
        "dataSetId": 1533183997317,
        "metadata": {
            "Class Description": "HIERARCHY",
            "Classification": "HIER",
            "GL Account": "287839.0000.109.??????.???",
            "P&ID": "KL47DSF3001",
            "Primary Craft": "ROTATING",
            "Primary OTSU": "A1-20.01",
            "Priority": "99",
            "PublishEventDate": "2024-12-03T21:13:31.186Z",
            "Site": "KL47",
            "Unit": "DS",
            "lastUpdatedTime": "2024-12-03 21:18:45.869",
            "locationLocationsID": "105876",
            "locationParentID": "12966",
            "location_Location": "DS/NH3/DINGS/628-3-I/728-2-FLOT",
            "site_location": "KL47-DS/NH3/DINGS/628-3-I/728-2-FLOT",
            "site_unit_tag": "KL47-DS-728-2-FLOT",
            "unit_tag": "DS-728-2-FLOT",
        },
        "source": "Source",
        "id": 6883648116577692,
        "createdTime": 1725418203378,
        "lastUpdatedTime": 1739885214893,
        "rootId": 4045609384782306,
    }

    node = {
        "space": "domain_asset",
        "externalId": "Asset 105876",
        "version": 21,
        "lastUpdatedTime": 1740174804685,
        "createdTime": 1740172064293,
        "instanceType": "node",
        "properties": {
            "sp_neat_enterprise": {
                "NeatAsset/v1": {
                    "dataSetId": {"space": "sp_neat_source", "externalId": "DOMAIN_ASSET"},
                    "classicExternalId": "Asset 105876",
                    "path": [
                        {"space": "domain_asset", "externalId": "Asset 12966"},
                        {"space": "domain_asset", "externalId": "Asset 105876"},
                    ],
                    "root": {"space": "domain_asset", "externalId": "Asset 12966"},
                    "parent": {"space": "domain_asset", "externalId": "Asset 12966"},
                    "pathLastUpdatedTime": "2025-02-21T21:53:24.685009+00:00",
                    "name": "347",
                    "description": "Lube oil system",
                    "source": {"space": "sp_neat_source", "externalId": "Source"},
                    "pId": "KL47DSF3001",
                    "Site": "KL47",
                    "Unit": "DS",
                    "Priority": 99,
                    "unit_tag": "DS-728-2-FLOT",
                    "GLAccount": "287839.0000.109.??????.???",
                    "primaryOTSU": "A1-20.01",
                    "primaryCraft": "ROTATING",
                    "site_location": "KL47-DS/NH3/DINGS/628-3-I/728-2-FLOT",
                    "site_unit_tag": "KL47-DS-728-2-FLOT",
                    "Classification": "HIER",
                    "PublishEventDate": "2024-12-03T21:13:31.186+00:00",
                    "classDescription": "HIERARCHY",
                    "locationParentID": 12966,
                    "location_Location": "DS/NH3/DINGS/628-3-I/728-2-FLOT",
                    "mylastUpdatedTime": "2024-12-03T21:18:45.869+00:00",
                    "locationLocationsID": 105876,
                }
            }
        },
        "type": {"space": "sp_neat_enterprise", "externalId": "NeatAsset"},
    }
    return node, asset


class TestAsClassic:
    def test_as_classic_asset(self, migrated_asset: tuple[dict[str, Any], dict[str, Any]]) -> None:
        node_data, asset_data = migrated_asset
        node = Node._load(node_data)
        asset = Asset._load(asset_data)

        assert as_classic(node, asset) == asset
