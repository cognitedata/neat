import time
from pathlib import Path
from typing import ClassVar

from cognite.neat._issues.errors import WorkflowStepNotInitializedError
from cognite.neat._workflows.model import FlowMessage
from cognite.neat._workflows.steps.data_contracts import NeatGraph
from cognite.neat._workflows.steps.step_model import Configurable, Step

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
            name="File path",
            value="staging/graph_export.ttl",
            label=("Relative path for the RDF file storage, " "must end with .ttl !"),
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, store: NeatGraph
    ) -> FlowMessage:  # type: ignore[syntax]
        if self.configs is None or self.data_store_path is None:
            raise WorkflowStepNotInitializedError(type(self).__name__)

        storage_path = self.data_store_path / Path(self.configs["File path"])
        relative_graph_file_path = str(storage_path).split("/data/")[1]

        store.graph.graph.serialize(str(storage_path), format="turtle")

        output_text = (
            "<p></p>"
            "Graph loaded to RDF file can be downloaded here : "
            f'<a href="/data/{relative_graph_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)
