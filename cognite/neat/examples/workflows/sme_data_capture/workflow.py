import logging
from pathlib import Path
import time

from cognite.client import CogniteClient
from cognite.neat.core import extractors, loader, parser
from cognite.neat.core.data_classes.transformation_rules import TransformationRules
from cognite.neat.core.extractors.rdf_to_assets import categorize_assets, rdf2assets, upload_assets
from cognite.neat.core.loader.graph_store import NeatGraphStore
from cognite.neat.core.utils import add_triples
from cognite.neat.core.validator import validate_asset_hierarchy
from cognite.neat.core.workflow import utils

from cognite.neat.core.workflow.base import BaseWorkflow
from cognite.neat.core.workflow.cdf_store import CdfStore
from cognite.neat.core.workflow.model import FlowMessage
from cognite.client.data_classes import AssetFilter


class SmeDataCaptureNeatWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.counter = 0
        self.metrics.register_metric("counter_1", "", "counter", ["step"])
        self.metrics.register_metric("gauge_1", "", "gauge", ["step"])
        self.transformation_rules: TransformationRules = None
        self.solution_graph: NeatGraphStore = None
        self.dataset_id: int = 0
   
    def step_run_experiment_1(self, flow_msg: FlowMessage = None):
        logging.info("Running experiment 1")
        logging.info(flow_msg.payload)
        self.counter = self.counter + 1
        logging.info("Counter: " + str(self.counter))
        
        self.metrics.get("counter_1", {"step": "run_experiment_1"}).inc()
        self.metrics.get("gauge_1", {"step": "run_experiment_1"}).set(self.counter)
        if flow_msg.payload["action"] == "approve":
            return FlowMessage(output_text=f"Running iteration {self.counter} of xperiment", next_step_ids=["cleanup"])
        else :
            return FlowMessage(output_text="Done running experiment", next_step_ids=["step_45507"])

    def step_cleanup(self, flow_msg: FlowMessage = None):
        logging.info("Cleanup")

    def step_error_handler(self, flow_msg: FlowMessage = None):
        logging.info("Error handler")
        return FlowMessage(output_text="Error handleed")

    def step_file_generator(self, flow_msg: FlowMessage = None):
        logging.info("File generator")
        # generate test file and save it to the file system 
        new_file_path = self.get_config_item_value("new_file_path")
        with open(new_file_path, "w") as f:
            f.write("Hello, World!")
        link_to_file = "http://localhost:8000/data/staging/new_file_test.txt"
        return FlowMessage(output_text=f"File generated and can be downloaded here : {link_to_file}")
    
    def step_load_transformation_rules(self, flow_msg: FlowMessage = None):
        # Load rules from file or remote location
        cdf_store = CdfStore(self.cdf_client, self.dataset_id, rules_storage_path=self.rules_storage_path)

        rules_file = self.get_config_item_value("rules.file")
        rules_file_path = Path(self.rules_storage_path, rules_file)
        version = self.get_config_item_value("rules.version")

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
        logging.info(f"Loaded prefixes {str(self.transformation_rules.prefixes)} rules")
        output_text = f"Loaded {len(self.transformation_rules.properties)} rules"
        logging.info(output_text)
        return FlowMessage(output_text=output_text)
    
    def step_configure_graph_store(self, flow_msg: FlowMessage = None):
        logging.info("Configure graph store")
        self.solution_graph = loader.NeatGraphStore(prefixes=self.transformation_rules.prefixes)
        self.solution_graph.init_graph("memory")
        return FlowMessage(output_text="Graph store configured")

    def step_generate_data_capture_sheet(self, flow_msg: FlowMessage = None):
        logging.info("Generate data capture sheet")
        sheet_name = self.get_config_item_value("data_capture.file", "data_capture.xlsx")
        data_capture_sheet_path = Path(self.rules_storage_path, sheet_name)
        extractors.rules2graph_capturing_sheet(self.transformation_rules, data_capture_sheet_path)
        output_text = f"Data capture sheet generated and can be downloaded here : http://localhost:8000/data/rules/{sheet_name}?{time.time()}"
        return FlowMessage(output_text=output_text)
    
    def step_process_data_capture_sheet(self, flow_msg: FlowMessage = None):
        logging.info("Process data capture sheet")
        sheet_name = self.get_config_item_value("data_capture.file", "data_capture.xlsx")
        data_capture_sheet_path = Path(self.rules_storage_path, sheet_name)
        raw_sheets = loader.graph_capturing_sheet.excel_file_to_table_by_name(data_capture_sheet_path)
        triples = extractors.sheet2triples(raw_sheets, self.transformation_rules)
        add_triples(self.solution_graph, triples)
        return FlowMessage(output_text=f"Data capture sheet processed")

    def step_prepare_cdf_assets(self, flow_msg: FlowMessage):
        # export graph into CDF
        # TODO : decide on error handling and retry logic\

        rdf_asset_dicts = rdf2assets(
            self.solution_graph,
            self.transformation_rules,
        )

        if not self.cdf_client:
            logging.info("Dry run, no CDF client available")
            return

        # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
        total_assets_before = self.cdf_client.assets.aggregate(
            filter=AssetFilter(data_set_ids=[{"id": self.dataset_id}])
        )[0]["count"]

        logging.info(f"Total count of assets in CDF before upload: { total_assets_before }")

        orphan_assets, circular_assets = validate_asset_hierarchy(rdf_asset_dicts)

        if orphan_assets:
            logging.error(f"Found orphaned assets: {', '.join(orphan_assets)}")

            orphanage_asset_external_id = (
                f"{self.transformation_rules.metadata.externalIdPrefix}orphanage"
                if self.transformation_rules.metadata.externalIdPrefix
                else "orphanage"
            )

            # Kill the process if you dont have orphanage asset in your asset hierarchy
            # and inform the user that it is missing !
            if orphanage_asset_external_id not in rdf_asset_dicts:
                msg = f"You dont have Orphanage asset {orphanage_asset_external_id} in asset hierarchy!"
                logging.error(msg)
                raise Exception(msg)

            logging.error("Orphaned assets will be assigned to 'Orphanage' root asset")

            for external_id in orphan_assets:
                rdf_asset_dicts[external_id]["parent_external_id"] = orphanage_asset_external_id

            orphan_assets, circular_assets = validate_asset_hierarchy(rdf_asset_dicts)

            logging.info(orphan_assets)
        else:
            logging.info("No orphaned assets found, your assets look healthy !")

        if circular_assets:
            msg = f"Found circular dependencies: {', '.join(circular_assets)}"
            logging.error(msg)
            raise Exception(msg)
        elif orphan_assets:
            msg = f"Not able to fix orphans: {', '.join(orphan_assets)}"
            logging.error(msg)
            raise Exception(msg)
        else:
            logging.info("No circular dependency among assets found, your assets hierarchy look healthy !")

        self.categorized_assets = categorize_assets(self.cdf_client, rdf_asset_dicts, self.dataset_id)

        count_create_assets = len(self.categorized_assets["create"])
        count_update_assets = len(self.categorized_assets["update"])
        count_decommission_assets = len(self.categorized_assets["decommission"])
        count_resurrect_assets = len(self.categorized_assets["resurrect"])

        self.count_create_assets = count_create_assets

        logging.info(f"Total count of assets to be created: { count_create_assets }")
        logging.info(f"Total count of assets to be updated: { count_update_assets }")
        logging.info(f"Total count of assets to be decommission: { count_decommission_assets }")
        logging.info(f"Total count of assets to be resurrect: { count_resurrect_assets }")

        msg = f"Total count of assets { len(rdf_asset_dicts) } of which: { count_create_assets } to be created"
        msg += f", { count_update_assets } to be updated"
        msg += f", { count_decommission_assets } to be decommissioned"
        msg += f", { count_resurrect_assets } to be resurrected"

        return FlowMessage(output_text=msg)

    def step_upload_cdf_assets(self, flow_msg: FlowMessage = None):
        if not self.cdf_client:
            logging.error("No CDF client available")
            raise Exception("No CDF client available")

        upload_assets(self.cdf_client, self.categorized_assets)
        for _ in range(1000):
            total_assets_after = self.cdf_client.assets.aggregate(
                filter=AssetFilter(data_set_ids=[{"id": self.dataset_id}])
            )[0]["count"]
            if total_assets_after >= self.count_create_assets:
                break
            logging.info(f"Waiting for assets to be created, current count {total_assets_after}")
            time.sleep(2)

        # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
        total_assets_after = self.cdf_client.assets.aggregate(
            filter=AssetFilter(data_set_ids=[{"id": self.dataset_id}])
        )[0]["count"]

        logging.info(f"Total count of assets in CDF after update: { total_assets_after }")
        self.categorized_assets = None  # free up memory after upload .
        return FlowMessage(output_text=f"Total count of assets in CDF after update: { total_assets_after }")

