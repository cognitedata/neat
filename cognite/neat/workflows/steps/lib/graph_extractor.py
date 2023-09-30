import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import ClassVar, cast

from rdflib import RDF, XSD, Literal, Namespace, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.graph import extractors
from cognite.neat.graph.extractors.mocks.graph import generate_triples as generate_mock_triples
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.utils.utils import add_triples
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "InstancesFromRdfFileToSourceGraph",
    "InstancesFromRulesToSolutionGraph",
    "InstancesFromGraphCaptureSpreadsheetToGraph",
    "GenerateMockGraph",
    "DataModelFromRulesToSourceGraph",
    "InstancesFromJsonToGraph",
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

    def run(self, rules: RulesData, source_graph: SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
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
        Configurable(name="file_name", value="graph_capture_sheet.xlsx", label="File name of the data capture sheet"),
        Configurable(name="storage_dir", value="staging", label="Directory to store data capture sheets"),
        Configurable(
            name="graph_name", value="solution", label="The name of target graph.", options=["source", "solution"]
        ),
    ]

    def run(self, transformation_rules: RulesData, graph_store: SolutionGraph | SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
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
            value='{"GeographicalRegion":5, "SubGeographicalRegion":10}',
            label="Target number of instances for each class",
        ),
        Configurable(
            name="graph_name", value="solution", label="The name of target graph.", options=["source", "solution"]
        ),
    ]

    def run(self, transformation_rules: RulesData, graph_store: SolutionGraph | SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
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

    def run(self, transformation_rules: RulesData, solution_graph: SolutionGraph) -> FlowMessage:  # type: ignore[override, syntax]
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

    def run(self, transformation_rules: RulesData, source_graph: SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
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
                    (rdf_instance_id, URIRef(ns + "hasParent"), URIRef(ns + "_" + cast(str, class_def.parent_class)))
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


class InstancesFromJsonToGraph(Step):
    """
    This step extracts instances from json file and loads them into a graph store. Warning : the step is experimental
    """

    description = "This step extracts instances from json file and loads them into a graph store"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name", value="data_dump.json", label="Full path to the file containing data dump in JSON format"
        ),
        Configurable(
            name="graph_name", value="solution", label="The name of target graph.", options=["source", "solution"]
        ),
        Configurable(
            name="object_id_generation_method",
            value="hash_of_json_element",
            label="Method to be used for generating object ids.  \
                 source_object_properties - takes multiple properties from the source object and concatenates them. \
                 source_object_id_mapping - takes a single property from the \
                 source object and maps it to a instance id. \
                      The option should be used when source object already contains stable ids \
                hash_of_json_element - takes a hash of the JSON element.Very generic method but \
                     can be slow working with big objects. \
                uuid - generates a random UUID, the option produces unstables ids . ",
            options=["source_object_properties", "source_object_id_mapping", "hash_of_json_element", "uuid"],
        ),
        Configurable(
            name="json_object_id_mapping",
            value="name",
            label="Comma separated list of object properties to be used for generating object ids. \
            Each property must be prefixed with the name of the object. For example: device:name,pump:id",
        ),
        Configurable(
            name="json_object_labels_mapping",
            value="",
            label="Comma separated list of object properties to be used for generating object labels. \
            Each property must be prefixed with the name of the object. For example: asset:name,asset:type",
        ),
        Configurable(
            name="namespace",
            value="http://purl.org/cognite/neat#",
            label="Namespace to be used for the generated objects.",
        ),
        Configurable(name="namespace_prefix", value="neat", label="The prefix to be used for the namespace."),
    ]

    def get_json_object_id(self, method, object_name: str, json_object: dict, parent_object_id: str, id_mapping: dict):
        if method == "source_object_properties":
            object_id = ""
            for property_name in id_mapping[object_name]:
                object_id += property_name + json_object[property_name]
        elif method == "hash_of_json_element":
            flat_json_object = {}
            for key, value in json_object.items():
                if not isinstance(value, dict) and not isinstance(value, list):
                    flat_json_object[key] = value

            object_id = json.dumps(flat_json_object, sort_keys=True)
        elif method == "uuid":
            return uuid.uuid4()
        elif method == "source_object_id_mapping":
            # don't hash existing valid ids
            try:
                return json_object[id_mapping[object_name][0]]
            except KeyError as e:
                # back to hashing
                logging.debug(f"Object {object_name} doesn't have a valid id.Error : {e}")
                object_id = self.get_json_object_id(
                    "hash_of_json_element", object_name, json_object, parent_object_id, id_mapping
                )
        else:
            raise ValueError(
                f"Unknown object_id_generation_method: {(self.configs or {}).get('object_id_generation_method')}"
            )

        return hashlib.sha256(object_id.encode()).hexdigest()

    def run(self, graph_store: SolutionGraph | SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None:
            raise StepNotInitialized(type(self).__name__)

        ns = PREFIXES["neat"]
        if Namespace(self.configs["namespace_prefix"]) != ns:
            ns = Namespace(self.configs["namespace"])
            graph_store.graph.graph.bind(self.configs["namespace_prefix"], ns)

        # self.graph.bind
        if self.configs["graph_name"] == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"])

        full_path = Path(self.data_store_path) / Path(self.configs["file_name"])
        logging.info(f"Loading data dump from {full_path}")
        with full_path.open() as f:
            json_data = json.load(f)

        graph = graph_store.graph.graph
        nodes_counter = 0
        property_counter = 0
        labels_mapping: dict | None = None
        object_id_mapping: dict | None = None
        if self.configs["json_object_labels_mapping"]:
            labels_mapping = {}
            for label_mapping in self.configs["json_object_labels_mapping"].split(","):
                object_name, property_name = label_mapping.split(":")
                labels_mapping[object_name] = property_name

        if self.configs["json_object_id_mapping"]:
            object_id_mapping = {}
            for id_mapping in self.configs["json_object_id_mapping"].split(","):
                if ":" not in id_mapping:
                    continue
                object_name, property_name = id_mapping.split(":")
                object_id_mapping[object_name] = (
                    # if multiple ids are used for the same object ,the order of the properties is important
                    object_id_mapping[object_name].append(property_name)
                    if object_name in object_id_mapping
                    else [property_name]
                )

        # Iterate through the JSON data and convert it to triples
        def convert_json_to_triples(data, parent_node, parent_object_id, parent_node_path, property_name=None):
            nonlocal nodes_counter, property_counter
            if isinstance(data, dict):
                if len(data) == 0:
                    return
                if property_name is None:
                    for key, value in data.items():
                        convert_json_to_triples(value, parent_node, parent_object_id, parent_node_path, key)
                else:
                    object_id = self.get_json_object_id(
                        self.configs["object_id_generation_method"],
                        property_name,
                        data,
                        parent_object_id,
                        object_id_mapping,
                    )
                    new_node = URIRef(ns + object_id)
                    graph.add((new_node, RDF.type, URIRef(ns + property_name)))
                    if labels_mapping and property_name in labels_mapping:
                        graph.add((new_node, URIRef(ns + "label"), Literal(data[labels_mapping[property_name]])))
                    else:
                        graph.add((new_node, URIRef(ns + "label"), Literal(property_name)))
                    graph.add((new_node, URIRef(ns + "parent"), parent_node))
                    nodes_counter += 1
                    for key, value in data.items():
                        new_node_path = parent_node_path + "/" + key
                        convert_json_to_triples(value, new_node, object_id, new_node_path, key)
            elif isinstance(data, list):
                if property_name is None:
                    for key, value in data.items():
                        convert_json_to_triples(value, parent_node, parent_object_id, parent_node_path, key)
                else:
                    for item in data:
                        convert_json_to_triples(item, parent_node, parent_object_id, parent_node_path, property_name)
            else:
                # Convert scalar values to RDF literals
                if isinstance(data, bool):
                    data = Literal(data, datatype=XSD.boolean)
                elif isinstance(data, int):
                    data = Literal(data, datatype=XSD.integer)
                elif isinstance(data, float):
                    data = Literal(data, datatype=XSD.float)
                elif isinstance(data, str):
                    data = Literal(data, datatype=XSD.string)
                else:
                    data = Literal(str(data))
                property_counter += 1
                graph.add((parent_node, URIRef(ns + property_name), data))

        # Start conversion with a root node
        root_node = URIRef(ns + "root")
        graph.add((root_node, URIRef(ns + "label"), Literal("root node")))
        graph.add((root_node, RDF.type, URIRef(ns + "root_node_id")))
        convert_json_to_triples(json_data, root_node, "root", "root", None)

        return FlowMessage(
            output_text=f"Data from source file imported successfully. Imported {nodes_counter} objects \
                            and {property_counter} properties ."
        )
