from cognite.neat.rules.importer._graph2rules import GraphImporter


def test_graph2tables_nordic44(source_knowledge_graph):
    graph_importer = GraphImporter(graph=source_knowledge_graph.graph, max_number_of_instance=1)
    rules, _, warnings = graph_importer.to_rules(return_report=True)

    assert len(rules.classes) == 59
    assert len(rules.properties) == 296
    assert len(warnings) == 402
    assert "Substation" in rules.classes
