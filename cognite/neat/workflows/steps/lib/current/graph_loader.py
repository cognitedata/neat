import time
from pathlib import Path
from typing import ClassVar, cast

from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import (
    SolutionGraph,
    SourceGraph,
)
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "GraphToRdfFile",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphToRdfFile(Step):
    """
    The step generates loads graph to RDF file
    """

    description = "The step generates nodes and edges from the graph"
    category = CATEGORY
    version = "private-beta"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Graph",
            value="source",
            options=["source", "solution"],
            label=("The graph to be used for loading RDF File." " Supported options : source, solution"),
        ),
        Configurable(
            name="File path",
            value="staging/graph_export.ttl",
            label=("Relative path for the RDF file storage, " "must end with .ttl !"),
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, graph: SourceGraph | SolutionGraph
    ) -> FlowMessage:  # type: ignore[syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        storage_path = self.data_store_path / Path(self.configs["File path"])
        relative_graph_file_path = str(storage_path).split("/data/")[1]

        graph_name = self.configs["Graph"] or "source"

        if graph_name == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"])

        graph.graph.serialize(str(storage_path), format="turtle")

        output_text = (
            "<p></p>"
            "Graph loaded to RDF file can be downloaded here : "
            f'<a href="/data/{relative_graph_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)
