import logging
from pathlib import Path
from cognite.neat.constants import PREFIXES

from cognite.neat.graph.stores import RdfStoreType
from cognite.neat.graph.stores import NeatGraphStore, drop_graph_store
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem
from cognite.neat.workflows.steps.step_model import Step

from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph

__all__ = ["ConfigureDefaultGraphStores", "LoadInstancesFromRdfFileToSourceGraph", "ResetGraphStores"]


class ConfigureDefaultGraphStores(Step):
    description = "The step initializes the source and solution graph stores."
    category = "graph_store"
    configuration_templates = [
        WorkflowConfigItem(
            name="source_rdf_store.type",
            value=RdfStoreType.OXIGRAPH,
            label="Data store type for source graph. Supported: oxigraph, memory,file, graphdb, sparql. ",
        ),
        WorkflowConfigItem(
            name="solution_rdf_store.type",
            value=RdfStoreType.OXIGRAPH,
            label="Data store type for solutioin graph. Supported: oxigraph, memory,file, graphdb, sparql",
        ),
        WorkflowConfigItem(
            name="source_rdf_store.disk_store_dir",
            value="source-graph-store",
            label="Local directory for source graph store",
        ),
        WorkflowConfigItem(
            name="solution_rdf_store.disk_store_dir",
            value="solution-graph-store",
            label="Local directory for solution graph store",
        ),
        WorkflowConfigItem(
            name="stores_to_configure",
            value="all",
            label="Defines which stores to configure. Possible values: all, source, solution",
        ),
        WorkflowConfigItem(
            name="solution_rdf_store.api_root_url",
            value="",
            label="Root url for graphdb or sparql endpoint",
        ),
    ]

    def run(self, rules_data: RulesData) -> FlowMessage | SourceGraph | SolutionGraph:
        logging.info("Initializing source graph")
        stores_to_configure = self.configs.get_config_item_value("stores_to_configure", "all")
        source_store_dir = self.configs.get_config_item_value("source_rdf_store.disk_store_dir", "source_graph")
        source_store_dir = Path(self.data_store_path) / Path(source_store_dir) if source_store_dir else None
        source_store_type = self.configs.get_config_item_value("source_rdf_store.type", RdfStoreType.MEMORY)
        if stores_to_configure in ["all", "source"]:
            if source_store_type == RdfStoreType.OXIGRAPH and "SourceGraph" in self.flow_context:
                return FlowMessage(output_text="Stores already configured")

            source_graph = NeatGraphStore(
                prefixes=rules_data.rules.prefixes, base_prefix="neat", namespace=PREFIXES["neat"]
            )
            source_graph.init_graph(
                source_store_type,
                self.configs.get_config_item_value("source_rdf_store.query_url", ""),
                self.configs.get_config_item_value("source_rdf_store.update_url", ""),
                "neat-tnt",
                internal_storage_dir=source_store_dir,
            )
            if stores_to_configure == "source":
                return FlowMessage(output_text="Source graph store configured successfully"), SourceGraph(
                    graph=source_graph
                )

        if stores_to_configure in ["all", "solution"]:
            solution_store_dir = self.configs.get_config_item_value(
                "solution_rdf_store.disk_store_dir", "solution_graph"
            )
            solution_store_dir = Path(self.data_store_path) / Path(solution_store_dir) if solution_store_dir else None
            solution_store_type = self.configs.get_config_item_value("solution_rdf_store.type", RdfStoreType.MEMORY)

            if solution_store_type == RdfStoreType.OXIGRAPH and "SolutionGraph" in self.flow_context:
                return FlowMessage(output_text="Stores already configured")
            solution_graph = NeatGraphStore(
                prefixes=rules_data.rules.prefixes, base_prefix="neat", namespace=PREFIXES["neat"]
            )

            solution_graph.init_graph(
                solution_store_type,
                self.configs.get_config_item_value("solution_rdf_store.query_url", ""),
                self.configs.get_config_item_value("solution_rdf_store.update_url", ""),
                "tnt-solution",
                internal_storage_dir=solution_store_dir,
            )

            solution_graph.graph_db_rest_url = self.configs.get_config_item_value("solution_rdf_store.api_root_url", "")
            if stores_to_configure == "solution":
                return FlowMessage(output_text="Solution graph store configured successfully"), SolutionGraph(
                    graph=solution_graph
                )

        return (
            FlowMessage(output_text="All graph stores configured successfully"),
            SourceGraph(graph=source_graph),
            SolutionGraph(graph=solution_graph),
        )


class ResetGraphStores(Step):
    description = "The step resets graph stores to their initial state (clears all data)."
    category = "graph_store"

    def run(self) -> FlowMessage:
        source_store_type = self.configs.get_config_item_value("source_rdf_store.type", RdfStoreType.MEMORY)
        solution_store_type = self.configs.get_config_item_value("solution_rdf_store.type", RdfStoreType.MEMORY)
        if source_store_type == RdfStoreType.OXIGRAPH and solution_store_type == RdfStoreType.OXIGRAPH:
            if "SourceGraph" not in self.flow_context or "SolutionGraph" not in self.flow_context:
                source_store_dir = self.configs.get_config_item_value("source_rdf_store.disk_store_dir", "source_graph")
                solution_store_dir = self.configs.get_config_item_value(
                    "solution_rdf_store.disk_store_dir", "solution_graph"
                )
                source_store_dir = Path(self.data_store_path) / Path(source_store_dir) if source_store_dir else None
                solution_store_dir = (
                    Path(self.data_store_path) / Path(solution_store_dir) if solution_store_dir else None
                )
                if solution_store_dir:
                    drop_graph_store(None, Path(source_store_dir), force=True)
                if solution_store_dir:
                    drop_graph_store(None, Path(solution_store_dir), force=True)
            else:
                if "SourceGraph" in self.flow_context:
                    self.flow_context["SourceGraph"].graph.drop()
                if "SolutionGraph" in self.flow_context:
                    self.flow_context["SolutionGraph"].graph.drop()
        return FlowMessage(output_text="Stores Reset")


class LoadInstancesFromRdfFileToSourceGraph(Step):
    description = "The step loads instances from a file into the source graph.The file must be in RDF format."
    category = "graph_loader"
    configuration_templates = [
        WorkflowConfigItem(
            name="source_rdf_store.file",
            value="source-graphs/source-graph-dump.xml",
            label="File name of source graph data dump in RDF format",
        )
    ]

    def run(self, rules: RulesData, source_graph: SourceGraph) -> FlowMessage:
        if source_graph.graph.rdf_store_type.lower() in ("memory", "oxigraph"):
            if source_file := self.configs.get_config_item_value("source_rdf_store.file"):
                source_graph.graph.import_from_file(Path(self.data_store_path) / Path(source_file))
                logging.info(f"Loaded {source_file} into source graph.")
            else:
                raise ValueError("You need a source_rdf_store.file specified for source_rdf_store.type=memory")
        else:
            raise NotImplementedError(f"Graph type {source_graph.graph.rdf_store_type} is not supported.")

        return FlowMessage(output_text="Instances loaded to source graph")
