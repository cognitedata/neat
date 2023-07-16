from typing import Optional

from cognite.neat.core import loader
from cognite.neat.core.extractors import upload_labels
from cognite.neat.core.rules import load_rules_from_excel_file
from cognite.neat.core.workflow2.base import Step
from cognite.neat.core.workflow2.data import ClientData, PathData, RulesData, SourceGraphData

__all__ = [
    "LoadTransformationRules",
    "ConfiguringStores",
    "LoadInstancesToGraph",
    "CreateCDFLabels",
    "PrepareCDFAssets",
]


class LoadTransformationRules(Step):
    def run(self, input_data: PathData) -> RulesData:
        rules = load_rules_from_excel_file(input_data.excel_file_path)
        return RulesData(rules=rules)


class ConfiguringStores(Step):
    def run(self, input_data: RulesData) -> SourceGraphData:
        rules = input_data.rules
        graph = loader.NeatGraphStore(prefixes=rules.prefixes, namespace=rules.metadata.namespace)
        graph.init_graph(base_prefix=rules.metadata.prefix)
        return SourceGraphData(graph=graph)


class LoadInstancesToGraph(Step):
    def run(self, rules: RulesData, graph_data: SourceGraphData) -> None:
        triples = rules.rules.instances
        for triple in triples:
            graph_data.graph.graph.add(triple)


class CreateCDFLabels(Step):
    def run(self, rules: RulesData, client: ClientData) -> None:
        upload_labels(client.client, rules.rules, extra_labels=["non-historic", "historic"])


class PrepareCDFAssets(Step):
    def run(self, rules: RulesData, graph: SourceGraphData, client: Optional[ClientData]) -> None:
        raise NotImplementedError()
