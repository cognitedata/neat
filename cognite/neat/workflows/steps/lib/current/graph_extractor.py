import json
import logging
from pathlib import Path
from typing import ClassVar, cast

from cognite.neat.graph.extractors._mock_graph_generator import MockGraphGenerator
from cognite.neat.rules._shared import DMSRules, InformationRules
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import MultiRuleData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["GraphFromRdfFile", "GraphFromMockData"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphFromMockData(Step):
    """
    This step generate mock graph based on the defined classes and target number of instances
    """

    description = "This step generate mock graph based on the defined classes and target number of instances"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Class count",
            value="",
            label="Target number of instances for each class",
        ),
        Configurable(name="Graph", value="solution", label="The name of target graph.", options=["source", "solution"]),
    ]

    def run(  # type: ignore[override, syntax]
        self, rules: MultiRuleData, graph_store: SolutionGraph | SourceGraph
    ) -> FlowMessage:
        if self.configs is None:
            raise StepNotInitialized(type(self).__name__)

        if not rules.information and not rules.dms:
            return FlowMessage(
                error_text="Rules must be made either by Information Architect or DMS Architect!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        logging.info(50 * "#")
        logging.info(50 * "#")
        logging.info(self.configs["Class count"])
        try:
            class_count = json.loads(self.configs["Class count"]) if self.configs["Class count"] else {}
        except Exception:
            return FlowMessage(
                error_text="Defected JSON stored in class_count",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        if self.configs["Graph"] == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"])

        logging.info("Initiated generation of mock triples")

        extractor = MockGraphGenerator(cast(InformationRules | DMSRules, rules.information or rules.dms), class_count)

        graph_store.graph.add_triples(extractor.extract())

        return FlowMessage(output_text=f"Instances loaded to the {graph_store.__class__.__name__}")


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
