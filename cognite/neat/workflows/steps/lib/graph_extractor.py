import hashlib
import json
import logging
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import ClassVar, cast

from rdflib import RDF, XSD, Literal, Namespace, URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.graph import extractors
from cognite.neat.graph.extractors._mock_graph_generator import generate_triples as generate_mock_triples
from cognite.neat.rules.exporter._rules2triples import get_instances_as_triples
from cognite.neat.utils.utils import create_sha256_hash
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "ExtractGraphFromRdfFile",
    "ExtractGraphFromRulesInstanceSheet",
    "ExtractGraphFromGraphCapturingSheet",
    "ExtractGraphFromMockGraph",
    "ExtractGraphFromRulesDataModel",
    "ExtractGraphFromJsonFile",
    "ExtractGraphFromAvevaPiAssetFramework",
    "ExtractGraphFromDexpiFile",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class ExtractGraphFromRdfFile(Step):
    """
    This step extract instances from a file into the source graph. The file must be in RDF format.
    """

    description = "This step extract instances from a file into the source graph. The file must be in RDF format."
    version = "private-beta"
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

    def run(self, source_graph: SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        if source_graph.graph.rdf_store_type.lower() in ("memory", "oxigraph"):
            if source_file := self.configs["file_path"]:
                source_graph.graph.import_from_file(
                    self.data_store_path / Path(source_file),
                    mime_type=self.configs["mime_type"],  # type: ignore[arg-type]
                    add_base_iri=self.configs["add_base_iri"] == "True",
                )
                logging.info(f"Loaded {source_file} into source graph.")
            else:
                raise ValueError("You need a source_rdf_store.file specified for source_rdf_store.type=memory")
        else:
            raise NotImplementedError(f"Graph type {source_graph.graph.rdf_store_type} is not supported.")

        return FlowMessage(output_text="Instances loaded to source graph")


class ExtractGraphFromDexpiFile(Step):
    """
    This step converts DEXPI P&ID (XML) into Knowledge Graph
    """

    description = "This step converts DEXPI P&ID (XML) into Knowledge Graph"
    version = "private-alpha"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_path",
            value="source-graphs/dexpi-pid.xml",
            label="File path to DEXPI P&ID in XML format",
        ),
        Configurable(
            name="base_namespace",
            value="http://purl.org/cognite/neat#",
            label="Base namespace to be added to ids for all nodes found in P&ID",
        ),
    ]

    def run(self, source_graph: SourceGraph) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        file_path = self.configs.get("file_path")
        base_namespace = self.configs.get("base_namespace", None)

        if file_path:
            triples = extractors.DexpiXML(self.data_store_path / Path(file_path), base_namespace).extract()
            source_graph.graph.add_triples(triples, verbose=True)

            logging.info(f"Loaded {file_path} into source graph.")
        else:
            raise ValueError("You need a source_rdf_store.file specified")

        return FlowMessage(output_text="Instances loaded to source graph")


class ExtractGraphFromGraphCapturingSheet(Step):
    """
    This step extracts nodes and edges from graph capture spreadsheet and load them into graph
    """

    description = "This step extracts nodes and edges from graph capturing spreadsheet and load them into graph"
    version = "private-alpha"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_path",
            value="source-graphs/graph_capture_sheet.xlsx",
            label="File path to Graph Capturing Sheet",
        ),
        Configurable(
            name="base_namespace",
            value="http://purl.org/cognite/neat#",
            label="Base namespace to be added to ids for all nodes extracted from graph capturing spreadsheet",
        ),
        Configurable(
            name="graph_name",
            value="solution",
            label="The name of target graph to load nodes and edge sto.",
            options=["source", "solution"],
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, rules: RulesData, graph_store: SolutionGraph | SourceGraph
    ) -> FlowMessage:
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        file_path = self.configs.get("file_path")

        if file_path:
            logging.info(f"Processing graph capture sheet {self.data_store_path / Path(file_path)}")

            triples = extractors.GraphCapturingSheet(
                rules=rules.rules,
                filepath=self.data_store_path / Path(file_path),
                namespace=self.configs.get("base_namespace", None),
                use_source_ids=True,
            ).extract()

        else:
            raise ValueError("You need a source_rdf_store.file specified")

        if self.configs["graph_name"] == "solution":
            graph_store = cast(SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph_store = cast(SourceGraph, self.flow_context["SourceGraph"])

        graph_store.graph.add_triples(triples, verbose=True)  # type: ignore[arg-type]
        return FlowMessage(output_text="Graph capture sheet processed")


class ExtractGraphFromMockGraph(Step):
    """
    This step generate mock graph based on the defined classes and target number of instances
    """

    description = "This step extracts instances from graph capture spreadsheet and loads them into solution graph"
    version = "private-alpha"
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

    def run(  # type: ignore[override, syntax]
        self, transformation_rules: RulesData, graph_store: SolutionGraph | SourceGraph
    ) -> FlowMessage:
        if self.configs is None:
            raise StepNotInitialized(type(self).__name__)
        logging.info("Initiated generation of mock triples")
        try:
            class_count = json.loads(self.configs["class_count"])
        except Exception:
            return FlowMessage(
                error_text="Defected JSON stored in class_count",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        if self.configs["graph_name"] == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"])

        logging.info(class_count)
        logging.info(transformation_rules.rules.metadata.model_dump())
        try:
            triples = generate_mock_triples(transformation_rules=transformation_rules.rules, class_count=class_count)
        except Exception as e:
            return FlowMessage(error_text=f"Error: {e}", step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        logging.info("Adding mock triples to graph")
        graph_store.graph.add_triples(triples, verbose=True)  # type: ignore[arg-type]
        return FlowMessage(output_text=f"Mock graph generated containing total of {len(triples)} triples")


class ExtractGraphFromRulesInstanceSheet(Step):
    """
    This step extracts instances from Rules object and loads them into the graph
    """

    description = "This step extracts instances from Rules object and loads them into the graph."
    category = CATEGORY
    version = "private-alpha"

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="graph_name", value="solution", label="The name of target graph.", options=["source", "solution"]
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, transformation_rules: RulesData, graph_store: SolutionGraph | SourceGraph
    ) -> FlowMessage:
        triples = get_instances_as_triples(transformation_rules.rules)
        instance_ids = {triple[0] for triple in triples}
        output_text = f"Extracted {len(instance_ids)} instances out of"
        output_text += f"Loaded {len(triples)} statements defining"
        output_text += f" {len(instance_ids)} instances"

        if self.configs["graph_name"] == "solution":
            graph_store = cast(SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph_store = cast(SourceGraph, self.flow_context["SourceGraph"])

        try:
            graph_store.graph.add_triples(triples, verbose=True)  # type: ignore[arg-type]
        except Exception as e:
            return FlowMessage(error_text=f"Error: {e}", step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        return FlowMessage(output_text=output_text)


class ExtractGraphFromRulesDataModel(Step):
    """
    This step extracts data model from rules file and loads it into source graph
    """

    description = "This step extracts data model from rules file and loads it into source graph."
    category = CATEGORY
    version = "private-alpha"

    def run(  # type: ignore[override, syntax]
        self, transformation_rules: RulesData, source_graph: SourceGraph
    ) -> FlowMessage:
        ns = PREFIXES["neat"]
        classes = transformation_rules.rules.classes
        properties = transformation_rules.rules.properties
        counter = 0
        for class_name, class_def in classes.items():
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
            if property_def.expected_value_type.suffix not in ("string", "integer", "float", "boolean"):
                source_graph.graph.graph.add(
                    (
                        rdf_instance_id,
                        URIRef(ns + "connectedTo"),
                        URIRef(ns + "_" + property_def.expected_value_type.suffix),
                    )
                )
            counter += 1

        output_text = f"Loaded {counter} classes into source graph"
        return FlowMessage(output_text=output_text)


class ExtractGraphFromJsonFile(Step):
    """
    This step extracts instances from json file and loads them into a graph store. Warning : the step is experimental
    """

    description = "This step extracts instances from json file and loads them into a graph store"
    category = CATEGORY
    version = "private-alpha"
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
            if object_name in id_mapping:
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
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        # self.graph.bind
        if self.configs["graph_name"] == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph_store = cast(SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph_store = cast(SourceGraph, self.flow_context["SourceGraph"])

        ns = Namespace(self.configs["namespace"])
        graph_store.graph.graph.bind(self.configs["namespace_prefix"], ns)

        full_path = self.data_store_path / Path(self.configs["file_name"])
        logging.info(f"Loading data dump from {full_path}")
        with full_path.open() as f:
            json_data = json.load(f)

        graph = graph_store.graph
        nodes_counter = 0
        property_counter = 0
        labels_mapping: dict[str, str] = {}
        object_id_mapping: dict[str, list[str]] = {}
        if self.configs["json_object_labels_mapping"]:
            for label_mapping in self.configs["json_object_labels_mapping"].split(","):
                object_name, property_name = label_mapping.split(":")
                labels_mapping[object_name] = property_name

        if self.configs["json_object_id_mapping"]:
            for id_mapping in self.configs["json_object_id_mapping"].split(","):
                if ":" not in id_mapping:
                    continue
                object_name, property_name = id_mapping.split(":")
                # if multiple ids are used for the same object ,the order of the properties is important
                if object_name in object_id_mapping:
                    object_id_mapping[object_name].append(property_name)
                else:
                    object_id_mapping[object_name] = [property_name]

        # Iterate through the JSON data and convert it to triples
        def convert_json_to_triples(
            data: dict, parent_node: URIRef, parent_object_id: str, parent_node_path: str, property_name=None
        ):
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
                    graph.graph.add((new_node, RDF.type, URIRef(ns + property_name)))
                    if labels_mapping and property_name in labels_mapping:
                        graph.graph.add((new_node, URIRef(ns + "label"), Literal(data[labels_mapping[property_name]])))
                    else:
                        graph.graph.add((new_node, URIRef(ns + "label"), Literal(property_name)))
                    graph.graph.add((new_node, URIRef(ns + "parent"), parent_node))
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
                graph.graph.add((parent_node, URIRef(ns + property_name), data))

        # Start conversion with a root node
        root_node = URIRef(ns + "root")
        graph.graph.add((root_node, URIRef(ns + "label"), Literal("root node")))
        graph.graph.add((root_node, RDF.type, URIRef(ns + "root_node_id")))
        convert_json_to_triples(json_data, root_node, "root", "root", None)
        return FlowMessage(
            output_text=f"Data from source file imported successfully. Imported {nodes_counter} objects \
                            and {property_counter} properties ."
        )


class ExtractGraphFromAvevaPiAssetFramework(Step):
    """
    This step extracts instances from Aveva PI AF and loads them into a graph store. Warning : the step is experimental
    """

    description = "This step extracts instances from Aveva PI AF and loads them into a graph store"
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name",
            value="staging/pi_af_dump.xml",
            label="Full path to the file \
            containing data dump in XML format",
        ),
        Configurable(
            name="graph_name", value="solution", label="The name of target graph.", options=["source", "solution"]
        ),
        Configurable(
            name="root_node_external_id",
            value="root",
            label="External id of the root node. The node will be created if it doesn't exist",
        ),
        Configurable(
            name="root_node_name",
            value="root",
            label="Name of the root node. The node will be created if it doesn't exist",
        ),
        Configurable(
            name="root_node_type",
            value="Asset",
            label="Type of the root node. The node will be created if it doesn't exist",
        ),
        Configurable(
            name="namespace",
            value="http://purl.org/cognite/neat#",
            label="Namespace to be used for the generated objects.",
        ),
        Configurable(name="namespace_prefix", value="neat", label="The prefix to be used for the namespace."),
    ]

    def add_root_asset_to_source_graph(self) -> str:
        root_external_id = self.configs["root_node_external_id"]
        root_name = self.configs["root_node_name"]
        root_asset_type = self.configs["root_node_type"]
        rdf_root_instance_id = URIRef(self.ns + root_external_id)
        self.graph_store.graph.add((rdf_root_instance_id, URIRef(self.ns + "Name"), Literal(root_name)))
        self.graph_store.graph.add((rdf_root_instance_id, RDF.type, URIRef(self.ns + root_asset_type)))
        return root_external_id

    def run(  # type: ignore[override, syntax]
        self, flow_msg: FlowMessage, graph_store: SolutionGraph | SourceGraph
    ) -> FlowMessage:
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        if source_file := self.configs["file_name"]:
            source_pi_dump = Path(self.data_store_path) / source_file
        else:
            return FlowMessage(output_text="No source file specified", next_step_ids=["step_error_handler"])

        # self.graph.bind
        if self.configs["graph_name"] == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            self.graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"]).graph
        else:
            self.graph_store = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"]).graph

        self.ns = Namespace(self.configs["namespace"])
        self.graph_store.graph.bind(self.configs["namespace_prefix"], self.ns)

        cdf_root_instance_id = self.add_root_asset_to_source_graph()
        # Parse the XML data into an ElementTree object
        root = ET.parse(source_pi_dump).getroot()
        counter = 0
        root_af_element = root.find("AFDatabase/AFElement")
        logging.info(f"Found AFElement: {root_af_element}")

        def process_af_attribute(af_element, element_path=None, parent_element_id: str | None = None):
            name = af_element.find("Name").text
            name = name.replace(" ", "_")
            new_element_path = element_path + "/" + name
            element_id = "_" + create_sha256_hash(new_element_path)
            rdf_instance_id = URIRef(self.ns + element_id)
            self.graph_store.graph.add((rdf_instance_id, URIRef(self.ns + "Name"), Literal(name)))
            self.graph_store.graph.add((rdf_instance_id, RDF.type, URIRef(self.ns + "Attribute" + name)))
            self.graph_store.graph.add((rdf_instance_id, URIRef(self.ns + "Path"), Literal(new_element_path)))
            if parent_element_id:
                self.graph_store.graph.add(
                    (rdf_instance_id, URIRef(self.ns + "hasParent"), URIRef(self.ns + parent_element_id))
                )
            for child in af_element:
                if child.tag == "AFAttribute":
                    process_af_attribute(child, new_element_path, element_id)
                elif child.tag == "Name":
                    pass
                else:
                    try:
                        self.graph_store.graph.add((rdf_instance_id, URIRef(self.ns + child.tag), Literal(child.text)))
                    except Exception as e:
                        logging.error(f"Error parsing AFAttribute {name} : {e}")

        def process_af_element(af_element, element_path=None, parent_element_id: str | None = None) -> str:
            nonlocal counter
            name = af_element.find("Name").text
            template = None
            new_element_path = element_path + "/" + name
            element_id = "_" + create_sha256_hash(new_element_path)
            rdf_instance_id = URIRef(self.ns + element_id)
            self.graph_store.graph.add((rdf_instance_id, URIRef(self.ns + "Name"), Literal(name)))
            self.graph_store.graph.add((rdf_instance_id, URIRef(self.ns + "Path"), Literal(new_element_path)))
            if parent_element_id:
                self.graph_store.graph.add(
                    (rdf_instance_id, URIRef(self.ns + "hasParent"), URIRef(self.ns + parent_element_id))
                )

            for child in af_element:
                if child.tag == "Name":
                    pass
                if child.tag == "Template":
                    template = child.text
                if child.tag == "AFAttribute":
                    process_af_attribute(child, new_element_path, element_id)
                if child.tag == "AFElement":
                    counter += 1
                    process_af_element(child, new_element_path, element_id)
                else:
                    self.graph_store.graph.add((rdf_instance_id, URIRef(self.ns + child.tag), Literal(child.text)))

            if template:
                self.graph_store.graph.add((rdf_instance_id, RDF.type, URIRef(self.ns + template)))
            else:
                self.graph_store.graph.add((rdf_instance_id, RDF.type, URIRef(self.ns + "AFElement")))

            return element_id

        process_af_element(root_af_element, "root", cdf_root_instance_id)
        self.graph_store.restart()  # restarting the graph to release the memory
        return FlowMessage(output_text=f" {counter} PI assets loaded into the graph")

    def convert_attribute(self, attribute):
        if "{" not in attribute:
            return attribute
        attr_splitted = attribute.split("{")[-1].split("}")
        return attr_splitted[0] + "/" + attr_splitted[1]
