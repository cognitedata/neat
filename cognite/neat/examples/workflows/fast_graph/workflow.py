import contextlib
import logging
import time
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetFilter
from prometheus_client import Gauge

from cognite.neat.core import loader, parser
from cognite.neat.core.data_classes.transformation_rules import TransformationRules
from cognite.neat.core.extractors.labels import upload_labels
from cognite.neat.core.extractors.rdf_to_assets import categorize_assets, rdf2assets, upload_assets
from cognite.neat.core.extractors.rdf_to_relationships import (
    categorize_relationships,
    rdf2relationships,
    upload_relationships,
)
from cognite.neat.core.loader.graph_store import NeatGraphStore, drop_graph_store
from cognite.neat.core.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.core.validator import validate_asset_hierarchy
from cognite.neat.core.workflow import utils
from cognite.neat.core.workflow.base import BaseWorkflow, FlowMessage
from cognite.neat.core.workflow.cdf_store import CdfStore

with contextlib.suppress(ValueError):
    prom_cdf_resource_stats = Gauge(
        "neat_fast_graph_wf_cdf_resource_stats",
        "CDF resource stats before and after running fast_graph workflow",
        ["resource_type", "state"],
    )
with contextlib.suppress(ValueError):
    prom_data_issues_stats = Gauge("neat_fast_graph_wf_data_issues", "Data validation issues", ["type"])


class FastGraphNeatWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.dataset_id: int = 0
        self.current_step: str = None
        self.source_graph: NeatGraphStore = None
        self.solution_graph: NeatGraphStore = None
        self.transformation_rules: TransformationRules = None
        self.stop_on_error = False
        self.count_create_assets = 0
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
        logging.info(f"Loaded prefixes {str(self.transformation_rules.prefixes)} rules")
        output_text = f"Loaded {len(self.transformation_rules.properties)} rules"
        logging.info(output_text)
        return FlowMessage(output_text=output_text)

    def step_configuring_stores(self, flow_msg: FlowMessage = None, clean_start: bool = True):
        # Initialize source and solution graph stores . clean_start=True will delete all artifacts(files , locks , etc) from previous runs
        logging.info("Initializing source graph")
        source_store_dir = self.get_config_item_value("source_rdf_store.disk_store_dir", None)
        solution_store_dir = self.get_config_item_value("solution_rdf_store.disk_store_dir", None)
        source_store_dir = Path(source_store_dir) if source_store_dir else None
        solution_store_dir = Path(solution_store_dir) if solution_store_dir else None
        if clean_start:
            drop_graph_store(self.source_graph, source_store_dir)
            drop_graph_store(self.solution_graph, solution_store_dir)

        self.source_graph = loader.NeatGraphStore(
            prefixes=self.transformation_rules.prefixes, base_prefix="nordic44", namespace="http://purl.org/nordic44#"
        )
        self.graph_source_type = self.get_config_item_value("source_rdf_store.type", self.graph_source_type)
        self.source_graph.init_graph(
            self.graph_source_type,
            self.get_config_item_value("source_rdf_store.query_url"),
            self.get_config_item_value("source_rdf_store.update_url"),
            "neat-tnt",
            internal_storage_dir=source_store_dir,
        )
        self.solution_graph = loader.NeatGraphStore(prefixes=self.transformation_rules.prefixes)
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
                # Todo avoid hard-coding adjacent path
                graphs = Path(__file__).resolve().parent.parent.parent / "source_graphs"
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

    def step_create_cdf_labels(self, flow_msg: FlowMessage = None):
        logging.info("Creating CDF labels")
        upload_labels(self.cdf_client, self.transformation_rules, extra_labels=["non-historic", "historic"])

    def step_prepare_cdf_assets(self, flow_msg: FlowMessage):
        # export graph into CDF
        # TODO : decide on error handling and retry logic\

        rdf_asset_dicts = rdf2assets(
            self.solution_graph,
            self.transformation_rules,
            stop_on_exception=self.stop_on_error,
        )

        if not self.cdf_client:
            logging.info("Dry run, no CDF client available")
            return

        # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
        total_assets_before = self.cdf_client.assets.aggregate(
            filter=AssetFilter(data_set_ids=[{"id": self.dataset_id}])
        )[0]["count"]

        prom_cdf_resource_stats.labels(resource_type="asset", state="count_before_neat_update").set(total_assets_before)
        logging.info(f"Total count of assets in CDF before upload: { total_assets_before }")

        orphan_assets, circular_assets = validate_asset_hierarchy(rdf_asset_dicts)

        prom_data_issues_stats.labels(type="circular_assets").set(len(circular_assets))
        prom_data_issues_stats.labels(type="orphan_assets").set(len(orphan_assets))

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

        self.categorized_assets, report = categorize_assets(
            self.cdf_client, rdf_asset_dicts, self.dataset_id, return_report=True
        )

        count_create_assets = len(self.categorized_assets["create"])
        count_update_assets = len(self.categorized_assets["update"])
        count_decommission_assets = len(self.categorized_assets["decommission"])
        count_resurrect_assets = len(self.categorized_assets["resurrect"])

        prom_cdf_resource_stats.labels(resource_type="asset", state="create").set(count_create_assets)
        prom_cdf_resource_stats.labels(resource_type="asset", state="update").set(count_update_assets)
        prom_cdf_resource_stats.labels(resource_type="asset", state="decommission").set(count_decommission_assets)
        prom_cdf_resource_stats.labels(resource_type="asset", state="resurrect").set(count_resurrect_assets)

        self.count_create_assets = count_create_assets

        logging.info(f"Total count of assets to be created: { count_create_assets }")
        logging.info(f"Total count of assets to be updated: { count_update_assets }")
        logging.info(f"Total count of assets to be decommission: { count_decommission_assets }")
        logging.info(f"Total count of assets to be resurrect: { count_resurrect_assets }")

        msg = f"Total count of assets { len(rdf_asset_dicts) } of which: { count_create_assets } to be created"
        msg += f", { count_update_assets } to be updated"
        msg += f", { count_decommission_assets } to be decommissioned"
        msg += f", { count_resurrect_assets } to be resurrected"
        number_of_updates = len(report["decommission"])
        logging.info(f"Total number of updates: {number_of_updates}")
        if number_of_updates > int(self.get_config_item_value("update_upproval_threshold", 1000)):
            return FlowMessage(
                output_text=f"Very high number of updates({number_of_updates}) requeres manual approval",
                payload=report,
                next_step_ids=["asset_update_approval"],
            )
        return FlowMessage(output_text=msg, next_step_ids=["upload_cdf_assets"])

    def step_upload_cdf_assets(self, flow_msg: FlowMessage = None):
        if flow_msg:
            if "action" in flow_msg.payload and flow_msg.payload["action"] != "approve":
                raise Exception("Update not approved")

        if not self.cdf_client:
            logging.error("No CDF client available")
            raise Exception("No CDF client available")

        upload_assets(self.cdf_client, self.categorized_assets, max_retries=2, retry_delay=4)
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

        prom_cdf_resource_stats.labels(resource_type="asset", state="count_after_neat_update").set(total_assets_after)
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
        count_defined_relationships = len(rdf_relationships)
        count_create_relationships = len(self.categorized_relationships["create"])
        count_decommission_relationships = len(self.categorized_relationships["decommission"])
        count_resurrect_relationships = len(self.categorized_relationships["resurrect"])

        prom_cdf_resource_stats.labels(resource_type="relationships", state="defined").set(count_defined_relationships)
        prom_cdf_resource_stats.labels(resource_type="relationships", state="create").set(count_create_relationships)
        prom_cdf_resource_stats.labels(resource_type="relationships", state="decommission").set(
            count_decommission_relationships
        )
        prom_cdf_resource_stats.labels(resource_type="relationships", state="resurrect").set(
            count_resurrect_relationships
        )

        msg = f"Total count of relationships { count_defined_relationships } of which: { count_create_relationships } to be created"
        msg += f", { count_decommission_relationships } to be decommissioned"
        msg += f", { count_resurrect_relationships } to be resurrected"

        return FlowMessage(output_text=msg)

    def step_upload_cdf_relationships(self, flow_msg: FlowMessage = None):
        if not self.cdf_client:
            logging.error("No CDF client available")
            raise Exception("No CDF client available")

        upload_relationships(self.cdf_client, self.categorized_relationships, max_retries=2, retry_delay=4)

    def step_cleanup(self, flow_msg: FlowMessage):
        self.categorized_assets = None
        self.categorized_relationships = None
