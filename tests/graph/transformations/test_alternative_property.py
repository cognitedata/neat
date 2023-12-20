from rdflib import Literal

from cognite.neat.graph.loaders.core.rdf_to_assets import rdf2assets
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.graph.transformations.transformer import domain2app_knowledge_graph


def test_missing_name(source_knowledge_graph, transformation_rules):
    no_name_id = "2dd9017c-bdfb-11e5-94fa-c8f73332c8f4"

    # removing the name from the terminal with id 2dd9017c-bdfb-11e5-94fa-c8f73332c8f4
    # this will cause the name to be set to the terminal id
    source_knowledge_graph.graph.remove(
        (
            source_knowledge_graph.namespace[f"_{no_name_id}"],
            transformation_rules.prefixes["cim"]["IdentifiedObject.name"],
            None,
        )
    )

    tnt_knowledge_graph = domain2app_knowledge_graph(source_knowledge_graph, transformation_rules)

    assets = rdf2assets(
        NeatGraphStore(tnt_knowledge_graph),
        transformation_rules,
        data_set_id=123456,
    )

    assert assets[no_name_id]["name"] == no_name_id


def test_alias_name(source_knowledge_graph, transformation_rules):
    only_alias_name_id = "2dd903a3-bdfb-11e5-94fa-c8f73332c8f4"

    # removing the name from the terminal with id 2dd903a3-bdfb-11e5-94fa-c8f73332c8f4
    # and adding alias name which is used as alternative property for name
    source_knowledge_graph.graph.add(
        (
            source_knowledge_graph.namespace[f"_{only_alias_name_id}"],
            transformation_rules.prefixes["cim"]["IdentifiedObject.aliasName"],
            Literal("Terminal Alias Name"),
        )
    )
    source_knowledge_graph.graph.remove(
        (
            source_knowledge_graph.namespace[f"_{only_alias_name_id}"],
            transformation_rules.prefixes["cim"]["IdentifiedObject.name"],
            None,
        )
    )

    tnt_knowledge_graph = domain2app_knowledge_graph(source_knowledge_graph, transformation_rules)

    assets = rdf2assets(
        NeatGraphStore(tnt_knowledge_graph),
        transformation_rules,
        data_set_id=123456,
    )

    assert assets[only_alias_name_id]["name"] == "Terminal Alias Name"


def test_all_name_property(source_knowledge_graph, transformation_rules):
    all_names_id = "2dd903a0-bdfb-11e5-94fa-c8f73332c8f4"

    # adding alias name property for terminal
    source_knowledge_graph.graph.add(
        (
            source_knowledge_graph.namespace[f"_{all_names_id}"],
            transformation_rules.prefixes["cim"]["IdentifiedObject.aliasName"],
            Literal("Terminal Alias Name"),
        )
    )

    tnt_knowledge_graph = domain2app_knowledge_graph(source_knowledge_graph, transformation_rules)

    assets = rdf2assets(
        NeatGraphStore(tnt_knowledge_graph),
        transformation_rules,
        data_set_id=123456,
    )

    assert assets[all_names_id]["name"] == "T2"
    assert assets[all_names_id]["metadata"]["IdentifiedObject.aliasName"] == "Terminal Alias Name"
