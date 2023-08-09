import contextlib
import logging
import time
from typing import Tuple
from prometheus_client import Gauge
from cognite.neat.graph.loaders import upload_labels
from cognite.neat.graph.loaders.core.rdf_to_assets import (
    NeatMetadataKeys,
    categorize_assets,
    rdf2assets,
    remove_non_existing_labels,
    unique_asset_labels,
    upload_assets,
)
from cognite.neat.graph.loaders.core.rdf_to_relationships import (
    categorize_relationships,
    rdf2relationships,
    upload_relationships,
)
from cognite.neat.graph.loaders.validator import validate_asset_hierarchy
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigs
from cognite.neat.workflows.steps.step_model import Step
from cognite.client.data_classes import AssetFilter

from cognite.client import CogniteClient
from ..data_contracts import CategorizedAssets, CategorizedRelationships, RulesData, SolutionGraph

with contextlib.suppress(ValueError):
    prom_cdf_resource_stats = Gauge(
        "neat_graph_to_asset_hierarchy_wf_cdf_resource_stats",
        "CDF resource stats before and after running fast_graph workflow",
        ["resource_type", "state"],
    )
with contextlib.suppress(ValueError):
    prom_data_issues_stats = Gauge("neat_graph_to_asset_hierarchy_wf_data_issues", "Data validation issues", ["type"])


__all__ = [
    "CreateCDFLabels",
    "GenerateCDFAssetsFromGraph",
    "GenerateCDFRelationshipsFromGraph",
    "UploadCDFAssets",
    "UploadCDFRelationships",
]


class CreateCDFLabels(Step):
    description = "The step creates default NEAT labels in CDF"
    category = "cdf_resources"
    
    def run(self, rules: RulesData, cdf_client: CogniteClient) -> None:
        upload_labels(cdf_client, rules.rules, extra_labels=["non-historic", "historic"])


class GenerateCDFAssetsFromGraph(Step):
    description = "The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object"
    category = "cdf_resources"

    def run(
        self, rules: RulesData, cdf_client: CogniteClient, solution_graph: SolutionGraph, configs: WorkflowConfigs
    ) -> Tuple[FlowMessage, CategorizedAssets]:
        self.meta_keys = NeatMetadataKeys.load(
            configs.get_config_group_values_by_name("cdf.asset.metadata.", remove_group_prefix=True)
        )
        rdf_asset_dicts = rdf2assets(
            solution_graph.graph,
            rules.rules,
            stop_on_exception=True,
            meta_keys=self.meta_keys,
        )
        # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
        total_assets_before = cdf_client.assets.aggregate(filter=AssetFilter(data_set_ids=[{"id": rules.dataset_id}]))[
            0
        ]["count"]

        # Label Validation
        labels_before = unique_asset_labels(rdf_asset_dicts.values())
        logging.info(f"Assets have {len(labels_before)} unique labels: {', '.join(sorted(labels_before))}")

        rdf_asset_dicts = remove_non_existing_labels(cdf_client, rdf_asset_dicts)

        labels_after = unique_asset_labels(rdf_asset_dicts.values())
        removed_labels = labels_before - labels_after
        logging.info(
            f"Removed {len(removed_labels)} labels as these do not exists in CDF. "
            f"Removed labels: {', '.join(sorted(removed_labels))}"
        )
        ######################

        prom_cdf_resource_stats.labels(resource_type="asset", state="count_before_neat_update").set(total_assets_before)
        logging.info(f"Total count of assets in CDF before upload: { total_assets_before }")

        orphan_assets, circular_assets = validate_asset_hierarchy(rdf_asset_dicts)

        prom_data_issues_stats.labels(type="circular_assets").set(len(circular_assets))
        prom_data_issues_stats.labels(type="orphan_assets").set(len(orphan_assets))

        if orphan_assets:
            logging.error(f"Found orphaned assets: {', '.join(orphan_assets)}")

            orphanage_asset_external_id = (
                f"{rules.rules.metadata.externalIdPrefix}orphanage-{rules.dataset_id}"
                if rules.rules.metadata.externalIdPrefix
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
            msg = f"Found circular dependencies: {str(circular_assets)}"
            logging.error(msg)
            raise Exception(msg)
        elif orphan_assets:
            msg = f"Not able to fix orphans: {', '.join(orphan_assets)}"
            logging.error(msg)
            raise Exception(msg)
        else:
            logging.info("No circular dependency among assets found, your assets hierarchy look healthy !")

        categorized_assets, report = categorize_assets(
            cdf_client, rdf_asset_dicts, rules.dataset_id, return_report=True
        )

        count_create_assets = len(categorized_assets["create"])
        count_update_assets = len(categorized_assets["update"])
        count_decommission_assets = len(categorized_assets["decommission"])
        count_resurrect_assets = len(categorized_assets["resurrect"])

        prom_cdf_resource_stats.labels(resource_type="asset", state="create").set(count_create_assets)
        prom_cdf_resource_stats.labels(resource_type="asset", state="update").set(count_update_assets)
        prom_cdf_resource_stats.labels(resource_type="asset", state="decommission").set(count_decommission_assets)
        prom_cdf_resource_stats.labels(resource_type="asset", state="resurrect").set(count_resurrect_assets)

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

        return (FlowMessage(output_text=msg), CategorizedAssets(assets=categorized_assets))


class UploadCDFAssets(Step):
    description = "The step uploads categorized assets to CDF"
    category = "cdf_resources"
    
    def run(
        self, rules: RulesData, cdf_client: CogniteClient, categorized_assets: CategorizedAssets, flow_msg: FlowMessage
    ) -> FlowMessage:
        if flow_msg and flow_msg.payload and "action" in flow_msg.payload:
            if flow_msg.payload["action"] != "approve":
                raise Exception("Update not approved")

        upload_assets(cdf_client, categorized_assets.assets, max_retries=2, retry_delay=4)
        count_create_assets = len(categorized_assets.assets["create"])
        for _ in range(1000):
            total_assets_after = cdf_client.assets.aggregate(
                filter=AssetFilter(data_set_ids=[{"id": rules.dataset_id}])
            )[0]["count"]
            if total_assets_after >= count_create_assets:
                break
            logging.info(f"Waiting for assets to be created, current count {total_assets_after}")
            time.sleep(2)

        # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
        total_assets_after = cdf_client.assets.aggregate(filter=AssetFilter(data_set_ids=[{"id": rules.dataset_id}]))[
            0
        ]["count"]

        prom_cdf_resource_stats.labels(resource_type="asset", state="count_after_neat_update").set(total_assets_after)
        logging.info(f"Total count of assets in CDF after update: { total_assets_after }")
        categorized_assets.assets = None  # free up memory after upload .
        return FlowMessage(output_text=f"Total count of assets in CDF after update: { total_assets_after }")


class GenerateCDFRelationshipsFromGraph(Step):
    description = "The step generates relationships from the graph and saves them to CategorizedRelationships object"
    category = "cdf_resources"

    def run(
        self, rules: RulesData, cdf_client: CogniteClient, solution_graph: SolutionGraph
    ) -> Tuple[FlowMessage, CategorizedRelationships]:
        # create, categorize and upload relationships
        rdf_relationships = rdf2relationships(
            solution_graph.graph.get_graph(),
            rules.rules,
        )

        categorized_relationships = categorize_relationships(cdf_client, rdf_relationships, rules.dataset_id)
        count_defined_relationships = len(rdf_relationships)
        count_create_relationships = len(categorized_relationships["create"])
        count_decommission_relationships = len(categorized_relationships["decommission"])
        count_resurrect_relationships = len(categorized_relationships["resurrect"])

        prom_cdf_resource_stats.labels(resource_type="relationships", state="defined").set(count_defined_relationships)
        prom_cdf_resource_stats.labels(resource_type="relationships", state="create").set(count_create_relationships)
        prom_cdf_resource_stats.labels(resource_type="relationships", state="decommission").set(
            count_decommission_relationships
        )
        prom_cdf_resource_stats.labels(resource_type="relationships", state="resurrect").set(
            count_resurrect_relationships
        )

        msg = (
            f"Total count of relationships { count_defined_relationships } of which:"
            f" { count_create_relationships } to be created"
        )
        msg += f", { count_decommission_relationships } to be decommissioned"
        msg += f", { count_resurrect_relationships } to be resurrected"

        return (FlowMessage(output_text=msg), CategorizedRelationships(relationships=categorized_relationships))


class UploadCDFRelationships(Step):
    description = "The step uploads relationships to CDF"
    category = "cdf_resources"

    def run(self, cdf_client: CogniteClient, categorized_relationships: CategorizedRelationships) -> FlowMessage:
        upload_relationships(cdf_client, categorized_relationships.relationships, max_retries=2, retry_delay=4)
        return FlowMessage(output_text="CDF relationships uploaded successfully")
