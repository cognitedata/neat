import pytest
from cognite.client.data_classes.data_modeling import DataModel as CogniteDataModel
from rdflib import URIRef
from yaml import safe_load

from cognite.neat.legacy.rules import examples, exceptions
from cognite.neat.legacy.rules.exporters._rules2pydantic_models import (
    rules_to_pydantic_models,
)
from cognite.neat.legacy.rules.importers._dms2rules import DMSImporter


def test_rules2pydantic_models(dms_compliant_rules, source_knowledge_graph):
    models = rules_to_pydantic_models(dms_compliant_rules, add_extra_fields=True)

    assert len(models) == 6
    assert set(models.keys()).issubset(set(dms_compliant_rules.classes.keys()))

    instance = models["Terminal"].from_graph(
        source_knowledge_graph,
        dms_compliant_rules,
        URIRef("http://purl.org/nordic44#_2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"),
    )

    assert instance.external_id == "2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"
    assert instance.name == "ARENDAL 300 A T1"
    assert instance.class_to_asset_mapping == {
        "metadata": ["mRID"],
        "name": ["name", "aliasName"],
    }

    asset = instance.to_asset(data_set_id=123456)

    assert asset.name == "ARENDAL 300 A T1"
    assert asset.metadata["type"] == "Terminal"


def test_views2pydantic_models(dms_compliant_rules, source_knowledge_graph):
    view = CogniteDataModel.load(safe_load(examples.power_grid_data_model.read_text())).views[3]

    rules = DMSImporter(views=[view]).to_rules(
        validators_to_skip=[
            "properties_refer_existing_classes",
            "is_type_defined_as_object",
        ]
    )

    models = rules_to_pydantic_models(rules, add_extra_fields=True)

    assert len(models) == 1
    assert set(models.keys()).issubset({"Terminal"})

    instance = models["Terminal"].from_graph(
        source_knowledge_graph,
        dms_compliant_rules,
        URIRef("http://purl.org/nordic44#_2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"),
    )

    assert instance.external_id == "2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"
    assert instance.name == "ARENDAL 300 A T1"

    node = instance.to_node()
    assert node.external_id == "2dd9019e-bdfb-11e5-94fa-c8f73332c8f4"
    assert node.space == "workshop"

    # there is no class_to_asset_mapping defined for this view so it should fail
    with pytest.raises(exceptions.ClassToAssetMappingNotDefined):
        _ = instance.to_asset(data_set_id=123456)
