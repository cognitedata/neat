"""Should contain methods to validate Graph Transformation Rules sheet,
as well App Data Model (RDF)
"""

import logging
from typing import List, Tuple

from cognite.client.data_classes import Asset


def _find_circular_reference_path(asset: Asset, assets: dict[str, Asset], max_hierarchy_depth: int = 10000) -> List:
    original_external_id = asset.get("external_id")
    circle = [original_external_id]
    ref = assets.get(asset.get("parent_external_id"))

    hop = 0
    while ref is not None and hop < max_hierarchy_depth:
        hop += 1
        circle.append(ref.get("external_id"))
        if len(circle) != len(set(circle)):
            msg = f"Found circular reference in asset hierarchy which starts with {original_external_id} and enters loop at {circle[-1]}. "
            logging.error(msg)
            return circle

        ref = assets.get(ref.get("parent_external_id"))

    if hop >= max_hierarchy_depth:
        msg = f"Your asset hierarchy is too deep. Max depth is {max_hierarchy_depth}. You probably have a circular reference."
        logging.error(msg)
        return circle
    else:
        return []


def validate_asset_hierarchy(assets: dict[str, dict]) -> Tuple[List[str], List[List[str]]]:
    """Validates asset hierarchy and reports on orphan assets and circular dependency

    Parameters
    ----------
    assets : dict[str, Asset]
        A dictionary of assets with external_id as key

    Returns
    -------
    Tuple[List[Asset], List[List[str]]
        List of orphan assets external ids and list of circular path of external ids.
        If both lists are empty, the hierarchy is healthy.
    """
    orphan_assets = []
    circular_reference_paths = []
    for asset in assets.values():
        parent_external_id = asset.get("parent_external_id")
        if parent_external_id is not None and parent_external_id not in assets:
            msg = (
                f"Found orphan asset {asset.get('external_id')} with parent {parent_external_id} which does not exist."
            )
            logging.error(msg)
            orphan_assets.append(asset.get("external_id"))
        circular_reference_path = _find_circular_reference_path(asset, assets)
        if not len(circular_reference_path):
            continue

        # Save the circle only once, not once for every asset
        if set(circular_reference_path) in [set(path) for path in circular_reference_paths]:
            continue
        circular_reference_paths.append(circular_reference_path)
    return orphan_assets, circular_reference_paths
