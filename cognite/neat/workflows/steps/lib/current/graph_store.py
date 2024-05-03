import logging
from pathlib import Path
from typing import ClassVar, cast

from cognite.neat.constants import PREFIXES
from cognite.neat.legacy.graph import stores
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["GraphStoreConfiguration", "GraphStoreReset"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphStoreConfiguration(Step):
    """
    This step initializes source OR solution graph store
    """

    description = "This step initializes the source and solution graph stores."
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Graph",
            value="source",
            label="Graph categorization, supported: source, solution ",
            options=["source", "solution"],
        ),
        Configurable(
            name="Graph store type",
            value=stores.OxiGraphStore.rdf_store_type,
            label="Graph store type, supported: oxigraph, memory,file, graphdb, sparql. ",
            options=["oxigraph", "memory", "file", "graphdb", "sparql"],
        ),
        Configurable(
            name="Disk storage directory",
            value="source-graph-store",
            label="Local directory that is used as local graph store.Only for oxigraph, file store types",
        ),
        Configurable(name="Query URL", value="", label="Query URL for SPARQL endpoint. Only for SPARQL store type"),
        Configurable(name="Update URL", value="", label="Update URL for SPARQL endpoint. Only for SPARQL store type"),
        Configurable(name="GraphDB API root URL", value="", label="Root url for GraphDB. Only for graphdb"),
        Configurable(
            name="Init procedure",
            value="reset",
            label="Operations to be performed on the graph store as part of init and configuration process. \
              Supported options : reset, clear, none",
            options=["reset", "none"],
        ),
    ]

    def run(  # type: ignore[override]
        self, rules_data: RulesData | None = None
    ) -> (FlowMessage, SourceGraph | SolutionGraph):  # type: ignore[syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        logging.info("Initializing graph")
        store_dir = self.data_store_path / Path(value) if (value := self.configs["Disk storage directory"]) else None
        store_type = self.configs["Graph store type"]
        graph_name_mapping = {"source": "SourceGraph", "solution": "SolutionGraph"}

        graph_name = graph_name_mapping[self.configs["Graph"]]
        graph_store = cast(SourceGraph | SolutionGraph | None, self.flow_context.get(graph_name, None))
        if self.configs["Init procedure"] == "reset":
            logging.info("Resetting graph")
            reset_store(store_dir, graph_store.graph if graph_store else None)
            if graph_name in self.flow_context:
                del self.flow_context[graph_name]
            graph_store = None
            logging.info("Graph reset complete")

        prefixes = rules_data.rules.prefixes if rules_data else PREFIXES.copy()

        if store_type == stores.OxiGraphStore.rdf_store_type and graph_store is not None:
            # OXIGRAPH doesn't like to be initialized twice without a good reason
            graph_store.graph.upsert_prefixes(prefixes)
            return FlowMessage(output_text="Stores already configured")
        try:
            store_cls = stores.STORE_BY_TYPE[store_type]
        except KeyError:
            return FlowMessage(output_text="Invalid store type")

        new_graph_store = store_cls(prefixes=prefixes, base_prefix="neat", namespace=PREFIXES["neat"])
        new_graph_store.init_graph(
            self.configs["Query URL"],
            self.configs["Update URL"],
            "neat-tnt",
            internal_storage_dir=store_dir,
        )

        return (
            FlowMessage(output_text="Graph store configured successfully"),
            SourceGraph(graph=new_graph_store) if graph_name == "SourceGraph" else SolutionGraph(graph=new_graph_store),
        )


def reset_store(data_store_dir: Path | None, graph_store: stores.NeatGraphStoreBase | None = None):
    if isinstance(graph_store, stores.OxiGraphStore):
        if graph_store:
            graph_store.close()
            graph_store.drop_graph_store_storage(data_store_dir)
        elif data_store_dir:
            graph_store.drop_graph_store_storage(data_store_dir)
    elif isinstance(graph_store, stores.GraphDBStore):
        if graph_store:
            graph_store.drop()
            graph_store.reinitialize_graph()
    return None


class GraphStoreReset(Step):
    """
    This step resets graph stores to their initial state (clears all data)
    """

    description = "This step resets graph stores to their initial state (clears all data)."
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Graph",
            value="source",
            label="Graph store to be reset. Supported: solution, source ",
            options=["source", "solution"],
        )
    ]

    def run(self) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        graph_name_mapping = {"source": "SourceGraph", "solution": "SolutionGraph"}

        graph_name = graph_name_mapping[self.configs["Graph"]]
        graph_store = cast(SourceGraph | SolutionGraph | None, self.flow_context.get(graph_name, None))
        if graph_store is not None:
            reset_store(graph_store.graph.internal_storage_dir, graph_store.graph)
            if graph_name in self.flow_context:
                del self.flow_context[graph_name]
            return FlowMessage(output_text="Reset operation completed")
        else:
            return FlowMessage(output_text="Stores already reset")
