import logging
import time
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetFilter

from cognite.neat import rules
from cognite.neat.graph import extractors
from cognite.neat.graph.loaders.core.labels import upload_labels
from cognite.neat.graph.loaders.core.rdf_to_assets import categorize_assets, rdf2assets, upload_assets
from cognite.neat.graph.loaders.core.rdf_to_relationships import (
    categorize_relationships,
    rdf2relationships,
    upload_relationships,
)
from cognite.neat.graph.loaders.validator import validate_asset_hierarchy
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.rules.exporter import rules2graph_sheet
from cognite.neat.rules.models import TransformationRules
from cognite.neat.utils.utils import add_triples
from cognite.neat.workflows import utils
from cognite.neat.workflows.base import BaseWorkflow
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage


class SmeGraphCaptureBaseWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.counter = 0
        self.metrics.register_metric("counter_1", "", "counter", ["step"])
        self.metrics.register_metric("gauge_1", "", "gauge", ["step"])
        self.transformation_rules: TransformationRules = None
        self.solution_graph: NeatGraphStore = None
        self.dataset_id: int = 0
        self.upload_meta_object = None

    def step_cleanup(self, flow_msg: FlowMessage = None):
        logging.info("Cleanup")

    def step_error_handler(self, flow_msg: FlowMessage = None):
        logging.info("Error handler")
        return FlowMessage(output_text="Error handleed")

    # ----------------------------------------------------------------------------------
    # ------------------ Graph Capturing Sheet Generation ------------------------------
    # ----------------------------------------------------------------------------------

    def step_load_transformation_rules(self, flow_msg: FlowMessage = None):
        # Load rules from file or remote location
        self.upload_meta_object = flow_msg.payload
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

        self.transformation_rules = rules.parse_rules_from_excel_file(rules_file_path)
        self.dataset_id = self.transformation_rules.metadata.data_set_id
        logging.info(f"Loaded prefixes {self.transformation_rules.prefixes!s} rules")
        output_text = f"Loaded {len(self.transformation_rules.properties)} rules"
        logging.info(output_text)
        return FlowMessage(output_text=output_text)

    def step_configure_graph_store(self, flow_msg: FlowMessage = None):
        logging.info("Configure graph store")
        self.solution_graph = extractors.NeatGraphStore(prefixes=self.transformation_rules.prefixes)
        self.solution_graph.init_graph("memory")
        return FlowMessage(output_text="Graph store configured")

    def step_generate_graph_capture_sheet(self, flow_msg: FlowMessage = None):
        logging.info("Generate graph capture sheet")
        sheet_name = self.get_config_item_value("graph_capture.file", "graph_capture_sheet.xlsx")
        auto_identifier_type = self.get_config_item_value("graph_capture_sheet.auto_identifier_type", None)
        logging.info(f"Auto identifier type {auto_identifier_type}")
        data_capture_sheet_path = self.rules_storage_path.parent / "graph-sheets" / sheet_name

        rules2graph_sheet(self.transformation_rules, data_capture_sheet_path, auto_identifier_type=auto_identifier_type)

        output_text = (
            "Data capture sheet generated and can be downloaded here : "
            f'<a href="http://localhost:8000/data/graph-sheets/{sheet_name}?{time.time()}" target="_blank">'
            f"{sheet_name}</a>"
        )

        return FlowMessage(output_text=output_text)

    # ----------------------------------------------------------------------------------
    # ------------------ Graph Capturing Sheet Processing ------------------------------
    # ----------------------------------------------------------------------------------

    def step_process_graph_capture_sheet(self, flow_msg: FlowMessage = None):
        data_capture_sheet_path = Path(self.upload_meta_object["full_path"])
        logging.info(f"Processing data capture sheet {data_capture_sheet_path}")

        triples = extractors.extract_graph_from_sheet(data_capture_sheet_path, self.solution_graph)
        add_triples(self.solution_graph, triples)
        return FlowMessage(output_text="Data capture sheet processed")

    def step_create_cdf_labels(self, flow_msg: FlowMessage = None):
        logging.info("Creating CDF labels")
        upload_labels(self.cdf_client, self.transformation_rules, extra_labels=["non-historic", "historic"])

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

        self.asset_count = {
            "create": len(self.categorized_assets["create"]),
            "update": len(self.categorized_assets["update"]),
            "decommission": len(self.categorized_assets["decommission"]),
            "resurrect": len(self.categorized_assets["resurrect"]),
        }

        for action, value in self.asset_count.items():
            logging.info(f"Total assets to {action}: {value}")

        msg = (
            f"Total count of assets { len(rdf_asset_dicts) } of which: { self.asset_count['create'] } to be created"
            f", { self.asset_count['update'] } to be updated"
            f", { self.asset_count['decommission'] } to be decommissioned"
            f", { self.asset_count['resurrect'] } to be resurrected"
        )
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
            if total_assets_after >= self.asset_count["create"]:
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

    def step_prepare_cdf_relationships(self, flow_msg: FlowMessage = None):
        # create, categorize and upload relationships
        rdf_relationships = rdf2relationships(
            self.solution_graph.get_graph(),
            self.transformation_rules,
        )
        if not self.cdf_client:
            logging.info("Dry run, no CDF client available")
            return

        self.categorized_relationships = categorize_relationships(self.cdf_client, rdf_relationships, self.dataset_id)

        self.relationship_count = {
            "create": len(self.categorized_relationships["create"]),
            "decommission": len(self.categorized_relationships["decommission"]),
            "resurrect": len(self.categorized_relationships["resurrect"]),
        }

        for action, value in self.relationship_count.items():
            logging.info(f"Total assets to {action}: {value}")

        msg = (
            f"Total count of reletions { len(rdf_relationships) } of which: "
            f"{ self.relationship_count['create'] } to be created"
            f", { self.asset_count['decommission'] } to be decommissioned"
            f", { self.asset_count['resurrect'] } to be resurrected"
        )

        return FlowMessage(output_text=msg)

    def step_upload_cdf_relationships(self, flow_msg: FlowMessage = None):
        if not self.cdf_client:
            logging.error("No CDF client available")
            raise Exception("No CDF client available")

        upload_relationships(self.cdf_client, self.categorized_relationships)
