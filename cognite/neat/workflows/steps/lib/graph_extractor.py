import json
import logging
from pathlib import Path
from typing import ClassVar

from rdflib import RDF, Literal, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.graph import extractors
from cognite.neat.graph.extractors.mocks.graph import generate_triples as generate_mock_triples
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.utils.utils import add_triples
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "InstancesFromRdfFileToSourceGraph",
    "InstancesFromRulesToSolutionGraph",
    "InstancesFromGraphCaptureSpreadsheetToGraph",
    "GenerateMockGraph",
    "DataModelFromRulesToSourceGraph",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class InstancesFromRdfFileToSourceGraph(Step):
    """
    This step extract instances from a file into the source graph. The file must be in RDF format.
    """

    description = "This step extract instances from a file into the source graph. The file must be in RDF format."
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_path",
            value="source-graphs/source-graph-dump.xml",
            label="File name of source graph data dump in RDF format",
        ),
        Configurable(
            name="mime_type",
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
            name="add_base_iri",
            value="True",
            label="Whether to add base IRI to graph in case if entity ids are relative",
            options=["True", "False"],
        ),
    ]

    def run(self, rules: RulesData, source_graph: SourceGraph) -> FlowMessage:
        if source_graph.graph.rdf_store_type.lower() in ("memory", "oxigraph"):
            if source_file := self.configs["file_path"]:
                source_graph.graph.import_from_file(
                    Path(self.data_store_path) / Path(source_file),
                    mime_type=self.configs["mime_type"],
                    add_base_iri=self.configs["add_base_iri"] == "True",
                )
                logging.info(f"Loaded {source_file} into source graph.")
            else:
                raise ValueError("You need a source_rdf_store.file specified for source_rdf_store.type=memory")
        else:
            raise NotImplementedError(f"Graph type {source_graph.graph.rdf_store_type} is not supported.")

        return FlowMessage(output_text="Instances loaded to source graph")


class InstancesFromGraphCaptureSpreadsheetToGraph(Step):
    """
    This step extracts instances from graph capture spreadsheet and loads them into solution graph
    """

    description = "This step extracts instances from graph capture spreadsheet and loads them into solution graph"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name",
            value="graph_capture_sheet.xlsx",
            label="File name of the data capture sheet",
        ),
        Configurable(name="storage_dir", value="staging", label="Directory to store data capture sheets"),
        Configurable(
            name="graph_name",
            value="solution",
            label="The name of target graph.",
            options=["source", "solution"],
        ),
    ]

    def run(
        self,
        transformation_rules: RulesData,
        graph_store: SolutionGraph | SourceGraph,
    ) -> FlowMessage:
        triggered_flow_message = self.flow_context["StartFlowMessage"]
        if "full_path" in triggered_flow_message.payload:
            data_capture_sheet_path = Path(triggered_flow_message.payload["full_path"])
        else:
            data_capture_sheet_path = (
                self.data_store_path / Path(self.configs["storage_dir"]) / self.configs["file_name"]
            )

        logging.info(f"Processing graph capture sheet {data_capture_sheet_path}")

        triples = extractors.extract_graph_from_sheet(
            data_capture_sheet_path, transformation_rule=transformation_rules.rules
        )

        graph_name = self.configs["graph_name"]
        if graph_name == "solution":
            graph_store = self.flow_context["SolutionGraph"]
        else:
            graph_store = self.flow_context["SourceGraph"]

        add_triples(graph_store.graph, triples)
        return FlowMessage(output_text="Graph capture sheet processed")


class GenerateMockGraph(Step):
    """
    This step generate mock graph based on the defined classes and target number of instances
    """

    description = "This step extracts instances from graph capture spreadsheet and loads them into solution graph"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="class_count",
            value='{"GeographicalRegion":5, "SubGeographicalRegion":10,}',
            label="Target number of instances for each class",
        ),
        Configurable(
            name="graph_name",
            value="solution",
            label="The name of target graph.",
            options=["source", "solution"],
        ),
    ]

    def run(
        self,
        transformation_rules: RulesData,
        graph_store: SolutionGraph | SourceGraph,
    ) -> FlowMessage:
        logging.info("Initiated generation of mock triples")
        try:
            class_count = json.loads(self.configs["class_count"])
        except Exception:
            return FlowMessage(
                error_text="Defected JSON stored in class_count",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        graph_name = self.configs["graph_name"]
        if graph_name == "solution":
            graph_store = self.flow_context["SolutionGraph"]
        else:
            graph_store = self.flow_context["SourceGraph"]

        logging.info(class_count)
        logging.info(transformation_rules.rules.metadata.model_dump())
        try:
            triples = generate_mock_triples(transformation_rules=transformation_rules.rules, class_count=class_count)
        except Exception as e:
            return FlowMessage(error_text=f"Error: {e}", step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        logging.info("Adding mock triples to graph")
        add_triples(graph_store.graph, triples)
        return FlowMessage(output_text=f"Mock graph generated containing total of {len(triples)} triples")


class InstancesFromRulesToSolutionGraph(Step):
    """
    This step extracts instances from rules file and loads them into solution graph
    """

    description = "This step extracts instances from rules file and loads them into solution graph."
    category = CATEGORY

    def run(self, transformation_rules: RulesData, solution_graph: SolutionGraph) -> FlowMessage:
        triples = get_instances_as_triples(transformation_rules.rules)
        instance_ids = {triple[0] for triple in triples}
        output_text = f"Extracted {len(instance_ids)} instances out of"

        try:
            for triple in triples:
                solution_graph.graph.graph.add(triple)
        except Exception as e:
            logging.error("Not able to load instances to source graph")
            raise e

        output_text = f"Loaded {len(triples)} statements defining"
        output_text += f" {len(instance_ids)} instances"
        return FlowMessage(output_text=output_text)


class DataModelFromRulesToSourceGraph(Step):
    """
    This step extracts data model from rules file and loads it into source graph
    """

    description = "This step extracts data model from rules file and loads it into source graph."
    category = CATEGORY

    def run(self, transformation_rules: RulesData, source_graph: SourceGraph) -> FlowMessage:
        ns = PREFIXES["neat"]
        clases = transformation_rules.rules.classes
        properties = transformation_rules.rules.properties
        counter = 0
        for class_name, class_def in clases.items():
            rdf_instance_id = URIRef(ns + "_" + class_def.class_id)
            source_graph.graph.graph.add((rdf_instance_id, URIRef(ns + "Name"), Literal(class_name)))
            source_graph.graph.graph.add((rdf_instance_id, RDF.type, URIRef(ns + class_def.class_id)))
            if class_def.parent_class:
                source_graph.graph.graph.add(
                    (rdf_instance_id, URIRef(ns + "hasParent"), URIRef(ns + "_" + class_def.parent_class))
                )
            counter += 1

        for _property_name, property_def in properties.items():
            rdf_instance_id = URIRef(ns + "_" + property_def.class_id)
            source_graph.graph.graph.add(
                (rdf_instance_id, URIRef(ns + property_def.property_id), Literal(property_def.expected_value_type))
            )
            if property_def.expected_value_type not in ("string", "integer", "float", "boolean"):
                source_graph.graph.graph.add(
                    (rdf_instance_id, URIRef(ns + "connectedTo"), URIRef(ns + "_" + property_def.expected_value_type))
                )
            counter += 1

        output_text = f"Loaded {counter} classes into source graph"
        return FlowMessage(output_text=output_text)
