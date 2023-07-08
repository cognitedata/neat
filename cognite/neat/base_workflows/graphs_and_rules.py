import logging
from pathlib import Path

from cognite.client import CogniteClient

from cognite.neat.core import loader, parser
from cognite.neat.core.configuration import PREFIXES
from cognite.neat.core.loader.graph_store import NeatGraphStore, drop_graph_store
from cognite.neat.core.rules.transformation_rules import TransformationRules
from cognite.neat.core.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.core.workflow import utils
from cognite.neat.core.workflow.base import BaseWorkflow, FlowMessage
from cognite.neat.core.workflow.cdf_store import CdfStore


class GraphsAndRulesBaseWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.dataset_id: int = 0
        self.source_graph: NeatGraphStore = None
        self.solution_graph: NeatGraphStore = None
        self.transformation_rules: TransformationRules = None
        self.graph_source_type = "memory"

    def step_load_transformation_rules(self, flow_msg: FlowMessage = None):
        # Load rules from file or remote location
        cdf_store = CdfStore(self.cdf_client, self.dataset_id, rules_storage_path=self.rules_storage_path)

        rules_file = self.get_config_item("rules.file").value
        rules_file_path = Path(self.rules_storage_path, rules_file)
        version = self.get_config_item("rules.version").value

        if rules_file_path.exists() and not version:
            logging.info(f"Loading rules from {rules_file_path}")
        elif rules_file_path.exists() and version:
            hash = utils.get_file_hash(rules_file_path)
            if hash != version:
                cdf_store.load_rules_file_from_cdf(rules_file, version)
        else:
            cdf_store.load_rules_file_from_cdf(self.cdf_client, version)

        tables = loader.rules.excel_file_to_table_by_name(rules_file_path)
        self.transformation_rules = parser.parse_transformation_rules(tables)
        self.dataset_id = self.transformation_rules.metadata.data_set_id
        logging.info(f"Loaded prefixes {str(self.transformation_rules.prefixes)} rules from {rules_file_path.name!r}.")
        output_text = f"Loaded {len(self.transformation_rules.properties)} rules"
        logging.info(output_text)
        return FlowMessage(output_text=output_text)

    def step_configuring_stores(self, flow_msg: FlowMessage = None, clean_start: bool = True):
        # Initialize source and solution graph stores . clean_start=True will delete all artifacts(files , locks , etc) from previous runs
        logging.info("Initializing source graph")
        self.graph_source_type = self.get_config_item_value("source_rdf_store.type", self.graph_source_type)
        source_store_dir = self.get_config_item_value("source_rdf_store.disk_store_dir", None)
        solution_store_dir = self.get_config_item_value("solution_rdf_store.disk_store_dir", None)
        source_store_dir = Path(self.data_store_path) / Path(source_store_dir) if source_store_dir else None
        solution_store_dir = Path(self.data_store_path) / Path(solution_store_dir) if solution_store_dir else None
        logging.info(f"source_store_dir={source_store_dir}")
        logging.info(f"solution_store_dir={solution_store_dir}")
        if clean_start:
            drop_graph_store(self.source_graph, source_store_dir, force=True)
            drop_graph_store(self.solution_graph, solution_store_dir, force=True)

        self.source_graph = loader.NeatGraphStore(
            prefixes=self.transformation_rules.prefixes, base_prefix="neat", namespace=PREFIXES["neat"]
        )

        if self.get_config_item_value("source_rdf_store.type"):
            self.source_graph.init_graph(
                self.get_config_item_value("source_rdf_store.type", self.graph_source_type),
                self.get_config_item_value("source_rdf_store.query_url"),
                self.get_config_item_value("source_rdf_store.update_url"),
                "neat-tnt",
                internal_storage_dir=source_store_dir,
            )

        if self.get_config_item_value("solution_rdf_store.type"):
            self.solution_graph = loader.NeatGraphStore(
                prefixes=self.transformation_rules.prefixes, base_prefix="neat", namespace=PREFIXES["neat"]
            )

            self.solution_graph.init_graph(
                self.get_config_item_value("solution_rdf_store.type"),
                self.get_config_item_value("solution_rdf_store.query_url"),
                self.get_config_item_value("solution_rdf_store.update_url"),
                "tnt-solution",
                internal_storage_dir=solution_store_dir,
            )

        self.solution_graph.graph_db_rest_url = self.get_config_item_value("solution_rdf_store.api_root_url")
        return

    def step_load_source_graph(self, flow_msg: FlowMessage = None):
        # Load graph into memory or GraphDB
        if self.graph_source_type.lower() == "graphdb":
            try:
                result = self.source_graph.query("SELECT DISTINCT ?class WHERE { ?s a ?class }")
            except Exception as e:
                logging.error(f"Failed to query most likely remote DB is not running {e}")
                raise Exception("Failed to query graph , most likely remote DB is not running") from e
            else:
                logging.info(f"Loaded {len(result.bindings)} classes")
        elif self.graph_source_type.lower() in ("memory", "oxigraph"):
            if source_file := self.get_config_item_value("source_rdf_store.file"):
                graphs = Path(self.data_store_path) / "source-graphs"
                self.source_graph.import_from_file(graphs / source_file)
                logging.info(f"Loaded {source_file} into source graph.")
            else:
                raise ValueError("You need a source_rdf_store.file specified for source_rdf_store.type=memory")
        else:
            raise NotImplementedError(f"Graph type {self.graph_source_type} is not supported.")

        self.solution_graph.drop()
        return

    def step_run_transformation(self, flow_msg: FlowMessage = None):
        report = RuleProcessingReport()
        # run transformation and generate new graph
        self.solution_graph.set_graph(
            domain2app_knowledge_graph(
                self.source_graph.get_graph(),
                self.transformation_rules,
                app_instance_graph=self.solution_graph.get_graph(),
                extra_triples=self.transformation_rules.instances,
                client=self.cdf_client,
                cdf_lookup_database=None,  # change this accordingly!
                processing_report=report,
            )
        )
        return FlowMessage(
            output_text=f"Total processed rules: { report.total_rules } , success: { report.total_success } , \
             no results: { report.total_success_no_results } , failed: { report.total_failed }",
            payload=report,
        )
