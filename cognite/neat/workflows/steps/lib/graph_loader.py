import logging
import time
from datetime import datetime
from typing import ClassVar, cast

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetFilter
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
from cognite.neat.graph.loaders.rdf_to_dms import rdf2nodes_and_edges, upload_edges, upload_nodes
from cognite.neat.graph.loaders.validator import validate_asset_hierarchy
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import (
    CategorizedAssets,
    CategorizedRelationships,
    Edges,
    Nodes,
    RulesData,
    SolutionGraph,
    SourceGraph,
)
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "CreateCDFLabels",
    "GenerateCDFAssetsFromGraph",
    "GenerateCDFRelationshipsFromGraph",
    "GenerateCDFNodesAndEdgesFromGraph",
    "UploadCDFAssets",
    "UploadCDFRelationships",
    "UploadCDFNodes",
    "UploadCDFEdges",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class CreateCDFLabels(Step):
    """
    This step creates default NEAT labels in CDF
    """

    description = "This step creates default NEAT labels in CDF"
    category = CATEGORY

    def run(self, rules: RulesData, cdf_client: CogniteClient) -> None:
        upload_labels(cdf_client, rules.rules, extra_labels=["non-historic", "historic"])


class GenerateCDFNodesAndEdgesFromGraph(Step):
    """
    The step generates nodes and edges from the graph
    """

    description = "The step generates nodes and edges from the graph"
    category = CATEGORY

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="graph_name",
            value="source",
            label=("The name of the graph to be used for matching." " Supported options : source, solution"),
        )
    ]

    def run(self, rules: RulesData, graph: SourceGraph | SolutionGraph) -> (FlowMessage, Nodes, Edges):
        graph_name = self.configs["graph_name"] or "source"
        if graph_name == "solution":
            graph = self.flow_context["SolutionGraph"]
        else:
            graph = self.flow_context["SourceGraph"]

        nodes, edges, exceptions = rdf2nodes_and_edges(graph.graph, rules.rules)

        msg = f"Total count of: <ul><li>{ len(nodes) } nodes</li><li>{ len(edges) } edges</li></ul>"

        if exceptions:
            file_name = f'nodes-and-edges-exceptions_{datetime.now().strftime("%Y%d%m%H%M")}.txt'
            exceptions_report_dir = self.data_store_path / "reports"
            exceptions_report_dir.mkdir(parents=True, exist_ok=True)
            exceptions_report_path = exceptions_report_dir / file_name

            exceptions_report_path.write_text(generate_exception_report(exceptions, "Errors"))
            msg += (
                f"<p>There is total of { len(exceptions) } exceptions</p>"
                f'<a href="http://localhost:8000/data/reports/{file_name}?{time.time()}" '
                f'target="_blank">here</a>'
            )

        return FlowMessage(output_text=msg), Nodes(nodes=nodes), Edges(edges=edges)


class UploadCDFNodes(Step):
    """
    This step uploads nodes to CDF
    """

    description = "This step uploads nodes to CDF"
    category = CATEGORY

    def run(self, cdf_client: CogniteClient, nodes: Nodes) -> FlowMessage:
        if nodes.nodes:
            upload_nodes(cdf_client, nodes.nodes, max_retries=2, retry_delay=4)
            return FlowMessage(output_text="CDF nodes uploaded successfully")
        else:
            return FlowMessage(output_text="No nodes to upload!")


class UploadCDFEdges(Step):
    """
    This step uploads edges to CDF
    """

    description = "This step uploads edges to CDF"
    category = CATEGORY

    def run(self, cdf_client: CogniteClient, edges: Edges) -> FlowMessage:
        if edges.edges:
            upload_edges(cdf_client, edges.edges, max_retries=2, retry_delay=4)
            return FlowMessage(output_text="CDF edges uploaded successfully")
        else:
            return FlowMessage(output_text="No edges to upload!")


class GenerateCDFAssetsFromGraph(Step):
    """
    The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object
    """

    description = (
        "The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object"
    )
    category = CATEGORY

    def run(
        self, rules: RulesData, cdf_client: CogniteClient, solution_graph: SolutionGraph
    ) -> (FlowMessage, CategorizedAssets):
        meta_keys = NeatMetadataKeys.load(self.configs)
        if self.metrics is None:
            raise ValueError(self._not_configured_message)
        prom_cdf_resource_stats = cast(
            Gauge,
            self.metrics.register_metric(
                "cdf_resources_stats",
                "CDF resource stats before and after running the workflow",
                m_type="gauge",
                metric_labels=["resource_type", "state"],
            ),
        )
        prom_data_issues_stats = cast(
            Gauge,
            self.metrics.register_metric(
                "data_issues_stats", "Data validation issues", m_type="gauge", metric_labels=["resource_type"]
            ),
        )

        rdf_asset_dicts = rdf2assets(solution_graph.graph, rules.rules, stop_on_exception=True, meta_keys=meta_keys)
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

        prom_data_issues_stats.labels(resource_type="circular_assets").set(len(circular_assets))
        prom_data_issues_stats.labels(resource_type="orphan_assets").set(len(orphan_assets))

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
            msg = f"Found circular dependencies: {circular_assets!s}"
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

        return FlowMessage(output_text=msg), CategorizedAssets(assets=categorized_assets)


class UploadCDFAssets(Step):
    """
    This step uploads categorized assets to CDF
    """

    description = "This step uploads categorized assets to CDF"
    category = CATEGORY

    def run(  # type: ignore[override]
        self, rules: RulesData, cdf_client: CogniteClient, categorized_assets: CategorizedAssets, flow_msg: FlowMessage
    ) -> FlowMessage:
        if flow_msg and flow_msg.payload and "action" in flow_msg.payload:
            if flow_msg.payload["action"] != "approve":
                raise Exception("Update not approved")
        if self.metrics is None:
            raise ValueError(self._not_configured_message)

        prom_cdf_resource_stats = cast(
            Gauge,
            self.metrics.register_metric(
                "cdf_resources_stats",
                "CDF resource stats before and after running the workflow",
                m_type="gauge",
                metric_labels=["resource_type", "state"],
            ),
        )
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
        del categorized_assets.assets  # free up memory after upload .
        return FlowMessage(output_text=f"Total count of assets in CDF after update: { total_assets_after }")


class GenerateCDFRelationshipsFromGraph(Step[CategorizedRelationships]):
    """
    This step generates relationships from the graph and saves them to CategorizedRelationships object
    """

    description = "This step generates relationships from the graph and saves them to CategorizedRelationships object"
    category = CATEGORY

    def run(  # type: ignore[override]
        self, rules: RulesData, cdf_client: CogniteClient, solution_graph: SolutionGraph
    ) -> (FlowMessage, CategorizedRelationships):
        # create, categorize and upload relationships
        rdf_relationships = rdf2relationships(solution_graph.graph, rules.rules)

        categorized_relationships = categorize_relationships(cdf_client, rdf_relationships, rules.dataset_id)
        count_defined_relationships = len(rdf_relationships)
        count_create_relationships = len(categorized_relationships["create"])
        count_decommission_relationships = len(categorized_relationships["decommission"])
        count_resurrect_relationships = len(categorized_relationships["resurrect"])

        if self.metrics is None:
            raise ValueError(self._not_configured_message)

        prom_cdf_resource_stats = cast(
            Gauge,
            self.metrics.register_metric(
                "cdf_resources_stats",
                "CDF resource stats before and after running the workflow",
                m_type="gauge",
                metric_labels=["resource_type", "state"],
            ),
        )

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

        return FlowMessage(output_text=msg), CategorizedRelationships(relationships=categorized_relationships)


class UploadCDFRelationships(Step):
    """
    This step uploads relationships to CDF
    """

    description = "This step uploads relationships to CDF"
    category = CATEGORY

    def run(  # type: ignore[override]
        self, client: CogniteClient, categorized_relationships: CategorizedRelationships
    ) -> FlowMessage:
        upload_relationships(client, categorized_relationships.relationships, max_retries=2, retry_delay=4)
        return FlowMessage(output_text="CDF relationships uploaded successfully")
