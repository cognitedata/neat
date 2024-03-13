import logging
from pathlib import Path
from typing import ClassVar

from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "GraphFromRdfFile",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphFromRdfFile(Step):
    """
    This step extract instances from a file into the source graph. The file must be in RDF format.
    """

    description = "This step extract instances from a file into the source graph. The file must be in RDF format."
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File path",
            value="source-graphs/source-graph-dump.xml",
            label="File name of source graph data dump in RDF format",
        ),
        Configurable(
            name="MIME type",
            value="application/rdf+xml",
            label="MIME type of file containing RDF graph",
            options=[
                "application/rdf+xml",
                "text/turtle",
                "application/n-triples",
                "application/n-quads",
                "application/trig",
            ],
        ),
        Configurable(
            name="Add base URI",
            value="True",
            label="Whether to add base URI to graph in case if entity ids are relative",
            options=["True", "False"],
        ),
    ]

    def run(self, source_graph: SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        if source_graph.graph.rdf_store_type.lower() in ("memory", "oxigraph"):
            if source_file := self.configs["File path"]:
                source_graph.graph.import_from_file(
                    self.data_store_path / Path(source_file),
                    mime_type=self.configs["MIME type"],  # type: ignore[arg-type]
                    add_base_iri=self.configs["Add base URI"] == "True",
                )
                logging.info(f"Loaded {source_file} into source graph.")
            else:
                raise ValueError("You need a source_rdf_store.file specified for source_rdf_store.type=memory")
        else:
            raise NotImplementedError(f"Graph type {source_graph.graph.rdf_store_type} is not supported.")

        return FlowMessage(output_text="Instances loaded to source graph")
