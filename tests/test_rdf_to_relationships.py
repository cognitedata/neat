from copy import deepcopy

from cognite.client.data_classes import Asset, AssetList, Label, LabelFilter, Relationship, RelationshipList
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.graph.loaders.cdfcore.rdf_to_assets import rdf2assets
from cognite.neat.graph.loaders.cdfcore.rdf_to_relationships import categorize_relationships, rdf2relationships
from cognite.neat.core.rules.exporter.cdf.rules2labels import get_labels


def test_relationship_diffing(mock_knowledge_graph, transformation_rules):
    cdf_relationship = rdf2relationships(mock_knowledge_graph, transformation_rules)

    # Categorize ids
    create_id = "SubGeographicalRegion-0:GeographicalRegion-0"
    resurrect_id = "GeographicalRegion-0:RootCIMNode-0"
    decommission_id = {
        "Substation-0:Terminal-0",
        "Terminal-0:Substation-0",
        "Substation-0:Terminal-1",
        "Terminal-1:Substation-0",
    }

    # Resurrect
    cdf_relationship.loc[cdf_relationship.external_id == resurrect_id, ["labels"]] = ["historic"]

    # Create
    ind = cdf_relationship[cdf_relationship.external_id == create_id].index
    cdf_relationship.drop(ind, inplace=True)

    # Here we are setting an asset to be historic, and accordingly we expect to see
    # two relationships being decommissioned, one for each direction.
    non_historic_assets = rdf2assets(mock_knowledge_graph, transformation_rules)
    historic_assets = {"Terminal-0": deepcopy(non_historic_assets["Terminal-0"])}
    historic_assets["Terminal-0"]["labels"] = ["historic"]
    non_historic_assets.pop("Terminal-0")

    with monkeypatch_cognite_client() as client_mock:

        def list_relationships(
            data_set_ids: int = 2626756768281823,
            limit: int = -1,
            labels=None,
            **_,
        ):
            labels = labels or LabelFilter(contains_any=["non-historic"])
            if labels == LabelFilter(contains_any=["non-historic"]):
                return RelationshipList(
                    [Relationship(**row) for _, row in cdf_relationship.iterrows() if "non-historic" in row.labels]
                )
            elif labels == LabelFilter(contains_any=["historic"]):
                return RelationshipList(
                    [Relationship(**row) for _, row in cdf_relationship.iterrows() if "historic" in row.labels]
                )
            else:
                return None

        def list_assets(
            data_set_ids: int = 2626756768281823,
            limit: int = -1,
            labels=None,
            **_,
        ):
            historic_asset_list = AssetList([Asset(**asset) for asset in historic_assets.values()])
            non_historic_asset_list = AssetList([Asset(**asset) for asset in non_historic_assets.values()])
            if labels == LabelFilter(contains_any=["non-historic"]):
                return non_historic_asset_list
            elif labels == LabelFilter(contains_any=["historic"]):
                return historic_asset_list
            else:
                return historic_asset_list + non_historic_asset_list

        def list_labels(**_):
            label_names = list(get_labels(transformation_rules)) + ["non-historic", "historic"]
            return [Label(external_id=label_name, name=label_names) for label_name in label_names]

        client_mock.labels.list = list_labels

        client_mock.relationships.list = list_relationships
        client_mock.assets.list = list_assets

    # Removing object from graph which should trigger decommissioning of relationships
    mock_knowledge_graph.graph.remove((transformation_rules.metadata.namespace["Terminal-1"], None, None))
    rdf_relationships = rdf2relationships(mock_knowledge_graph, transformation_rules)

    categorized_relationships, report = categorize_relationships(
        client=client_mock,
        rdf_relationships=rdf_relationships,
        data_set_id=transformation_rules.metadata.data_set_id,
        return_report=True,
    )

    assert len(categorized_relationships["create"]) == 1
    assert len(report["create"]) == 1
    assert create_id == categorized_relationships["create"][0].external_id
    assert create_id in report["create"]

    assert len(categorized_relationships["resurrect"]) == 1
    assert len(report["resurrect"]) == 1
    assert resurrect_id == categorized_relationships["resurrect"][0]._external_id
    assert resurrect_id in report["resurrect"]

    assert len(categorized_relationships["decommission"]) == 4
    assert len(report["decommission"]) == 4
    assert decommission_id == {relation._external_id for relation in categorized_relationships["decommission"]}
    assert decommission_id == report["decommission"]
