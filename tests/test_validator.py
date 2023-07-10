from cognite.neat.core.extractors.cdfcore.rdf_to_assets import rdf2assets
from cognite.neat.core.loader.graph_store import NeatGraphStore
from cognite.neat.core.validator import validate_asset_hierarchy


def test_orphan_assets(transformation_rules, solution_knowledge_graph):
    assets = rdf2assets(
        NeatGraphStore(solution_knowledge_graph),
        transformation_rules,
    )

    asset_external_ids = [asset.get("external_id") for asset in assets.values()]

    # Create an orphan asset
    assets[asset_external_ids[0]]["parent_external_id"] = "DisappearingParent"

    orphan_assets, _ = validate_asset_hierarchy(assets)

    assert len(orphan_assets) == 1
    assert orphan_assets[0] == asset_external_ids[0]


def test_circular_assets(transformation_rules, solution_knowledge_graph):
    assets = rdf2assets(
        NeatGraphStore(solution_knowledge_graph),
        transformation_rules,
    )

    # Create a circular asset hierarchy
    assets["f176960e-9aeb-11e5-91da-b8763fd99c5f"]["parent_external_id"] = "2dd9017c-bdfb-11e5-94fa-c8f73332c8f4"
    assets["2dd9017c-bdfb-11e5-94fa-c8f73332c8f4"]["parent_external_id"] = "f176960e-9aeb-11e5-91da-b8763fd99c5f"

    _, circular_assets = validate_asset_hierarchy(assets)

    assert len(circular_assets) == 8
