import pytest
from rdflib import URIRef
from cognite.neat.rules.exporter.rules2pydantic_models import rules_to_pydantic_models


def test_rules2pydantic_models(transformation_rules, source_knowledge_graph):
    models = rules_to_pydantic_models(transformation_rules)

    assert len(models) == 6
    assert set(models.keys()).issubset(set(transformation_rules.classes.keys()))

    instance = models["Terminal"].from_graph(
        source_knowledge_graph,
        transformation_rules,
        URIRef("http://purl.org/nordic44#_2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"),
    )

    assert instance.external_id == "2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"
    assert instance.IdentifiedObject_name == "ARENDAL 300 A T1"
    assert instance.class_to_asset_mapping == {
        "metadata": ["IdentifiedObject.mRID"],
        "name": ["IdentifiedObject.name", "IdentifiedObject.aliasName"],
    }

    asset = instance.to_asset()

    assert asset.name == "ARENDAL 300 A T1"
    assert asset.metadata["type"] == "Terminal"
