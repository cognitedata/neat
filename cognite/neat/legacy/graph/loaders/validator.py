"""Should contain methods to validate Graph Transformation Rules sheet,
as well App Data Model (RDF)
"""

import logging
from typing import Any


def _find_circular_reference_path(
    asset: dict[str, Any], assets: dict[str, dict[str, Any]], max_hierarchy_depth: int = 10000
) -> list:
    original_external_id = asset.get("external_id", "")
    circle: list[str] = [original_external_id]
    parent_external_id = asset.get("parent_external_id")
    if isinstance(parent_external_id, str):
        ref = assets.get(parent_external_id)
    else:
        ref = None

    hop = 0
    while ref is not None and hop < max_hierarchy_depth:
        hop += 1
        if external_id := ref.get("external_id"):
            circle.append(external_id)
        if len(circle) != len(set(circle)):
            msg = (
                f"Found circular reference in asset hierarchy which starts with "
                f"{original_external_id} and enters loop at {circle[-1]}. "
            )
            logging.error(msg)
            return circle
        if parent_external_id := ref.get("parent_external_id"):
            ref = assets.get(parent_external_id)
        else:
            ref = None

    if hop >= max_hierarchy_depth:
        msg = (
            f"Your asset hierarchy is too deep. Max depth is {max_hierarchy_depth}. "
            "You probably have a circular reference."
        )
        logging.error(msg)
        return circle
    else:
        return []


def validate_asset_hierarchy(
    assets: dict[str, dict[str, Any]]
) -> tuple[list[str], list[list[str]], dict[str, list[str]]]:
    """Validates asset hierarchy and reports on orphan assets and circular dependency

    Args:
        assets : A dictionary of assets with external_id as key

    Returns:
        List of orphan assets external ids and list of circular path of external ids.
        If both lists are empty, the hierarchy is healthy.
    """
    orphan_assets: list[str] = []
    circular_reference_paths: list[list[str]] = []
    parent_children_map: dict[str, list[str]] = {}

    for asset in assets.values():
        parent_external_id = asset.get("parent_external_id")
        asset_extarnal_id = asset.get("external_id")
        if asset_extarnal_id and parent_external_id:
            if parent_external_id in parent_children_map:
                parent_children_map[parent_external_id].append(asset_extarnal_id)
            else:
                parent_children_map[parent_external_id] = [asset_extarnal_id]
        if parent_external_id is not None and parent_external_id not in assets:
            msg = (
                f"Found orphan asset {asset.get('external_id')} with parent {parent_external_id} which does not exist."
            )
            logging.error(msg)
            if external_id := asset.get("external_id"):
                orphan_assets.append(external_id)
        circular_reference_path = _find_circular_reference_path(asset, assets)
        if not len(circular_reference_path):
            continue

        # Save the circle only once, not once for every asset
        if set(circular_reference_path) in [set(path) for path in circular_reference_paths]:
            continue
        circular_reference_paths.append(circular_reference_path)
    return orphan_assets, circular_reference_paths, parent_children_map
