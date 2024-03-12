import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, cast

from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetFilter
from prometheus_client import Gauge

from cognite.neat.graph import loaders
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
from cognite.neat.graph.loaders.rdf_to_dms import upload_edges, upload_nodes
from cognite.neat.graph.loaders.validator import validate_asset_hierarchy
from cognite.neat.rules.models.rdfpath import TransformationRuleType
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows._exceptions import StepFlowContextNotInitialized, StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
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
    "GenerateAssetsFromGraph",
    "GenerateRelationshipsFromGraph",
    "GenerateNodesAndEdgesFromGraph",
    "LoadLabelsToCDF",
    "LoadAssetsToCDF",
    "LoadRelationshipsToCDF",
    "LoadNodesToCDF",
    "LoadEdgesToCDF",
    "LoadGraphToRdfFile",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class LoadLabelsToCDF(Step):
    """
    This step creates and loads default NEAT labels in CDF
    """

    description = "This step creates default NEAT labels in CDF"
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="data_set_id", value="", label=("CDF dataset id to which the labels will be added."))
    ]

    def run(self, rules: RulesData, cdf_client: CogniteClient) -> None:  # type: ignore[override, syntax]
        upload_labels(
            cdf_client,
            rules.rules,
            data_set_id=int(self.configs["data_set_id"]),
            extra_labels=["non-historic", "historic"],
        )


class GenerateNodesAndEdgesFromGraph(Step):
    """
    The step generates nodes and edges from the graph
    """

    description = "The step generates nodes and edges from the graph"
    category = CATEGORY

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="graph_name",
            value="source",
            options=["source", "solution"],
            label=("The name of the graph to be used for matching." " Supported options : source, solution"),
        ),
        Configurable(
            name="add_class_prefix",
            value="False",
            options=["True", "False"],
            label=("Whether to add class name as a prefix to external ids of instances or not"),
        ),
        Configurable(
            name="data_validation_error_handling_strategy",
            value="skip_and_report",
            options=["skip_and_report", "fail_and_report"],
            label=(
                "The strategy for handling data validation errors. Supported options: \
                   skip_and_report - failed instance (node or edge) will be skipped and reported , \
                   fail_and_report - failed instance  (node or edge) will fail the workflow and report the error"
            ),
        ),
        Configurable(
            name="apply_basic_transformation",
            value="True",
            options=["True", "False"],
            label=("Whether to apply basic transformations rules (rdfpath) or not. Default is True."),
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, rules: RulesData, graph: SourceGraph | SolutionGraph
    ) -> (FlowMessage, Nodes, Edges):  # type: ignore[syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        if self.flow_context is None:
            raise StepFlowContextNotInitialized(type(self).__name__)

        graph_name = self.configs["graph_name"] or "source"
        data_validation_error_handling_strategy = self.configs.get(
            "data_validation_error_handling_strategy", "skip_and_report"
        )
        if graph_name == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"])

        add_class_prefix = True if self.configs["add_class_prefix"] == "True" else False
        apply_basic_transformation = True if self.configs.get("apply_basic_transformation", "True") == "True" else False

        if apply_basic_transformation:
            final_rules = rules.rules
        else:
            logging.debug("Basic transformation rules are not applied to the graph")
            final_rules = rules.rules.model_copy(deep=True)
            prefix = final_rules.metadata.prefix
            for rule in final_rules.properties.values():
                rule.rule_type = TransformationRuleType.rdfpath
                rule.rule = f"{prefix}:{rule.class_id}({prefix}:{rule.property_id})"

        loader = loaders.DMSLoader(final_rules, graph.graph, add_class_prefix=add_class_prefix)
        nodes, edges, exceptions = loader.as_nodes_and_edges(stop_on_exception=False)

        msg = f"Total count of: <ul><li>{ len(nodes) } nodes</li><li>{ len(edges) } edges</li></ul>"

        if exceptions:
            file_name = f'nodes-and-edges-exceptions_{datetime.now().strftime("%Y%d%m%H%M")}.txt'
            exceptions_report_dir = self.data_store_path / "reports"
            exceptions_report_dir.mkdir(parents=True, exist_ok=True)
            exceptions_report_path = exceptions_report_dir / file_name

            exceptions_report_path.write_text(generate_exception_report(exceptions, "Errors"))
            msg += (
                f"<p>There is total of { len(exceptions) } exceptions</p>"
                f'<a href="/data/reports/{file_name}?{time.time()}" '
                f'target="_blank">Full error report </a>'
            )
            if data_validation_error_handling_strategy == "fail_and_report":
                return FlowMessage(error_text=msg, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        return FlowMessage(output_text=msg), Nodes(nodes=nodes), Edges(edges=edges)


class LoadGraphToRdfFile(Step):
    """
    The step generates loads graph to RDF file
    """

    description = "The step generates nodes and edges from the graph"
    category = CATEGORY
    version = "private-beta"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="graph_name",
            value="source",
            options=["source", "solution"],
            label=("The name of the graph to be used for loading RDF File." " Supported options : source, solution"),
        ),
        Configurable(
            name="rdf_file_path",
            value="staging/graph_export.ttl",
            label=("Relative path for the RDF file storage, " "must end with .ttl !"),
        ),
    ]

    def run(  # type: ignore[override, syntax]
        self, graph: SourceGraph | SolutionGraph
    ) -> FlowMessage:  # type: ignore[syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        storage_path = self.data_store_path / Path(self.configs["rdf_file_path"])
        relative_graph_file_path = str(storage_path).split("/data/")[1]

        graph_name = self.configs["graph_name"] or "source"

        if graph_name == "solution":
            # Todo Anders: Why is the graph fetched from context when it is passed as an argument?
            graph = cast(SourceGraph | SolutionGraph, self.flow_context["SolutionGraph"])
        else:
            graph = cast(SourceGraph | SolutionGraph, self.flow_context["SourceGraph"])

        graph.graph.serialize(str(storage_path), format="turtle")

        output_text = (
            "<p></p>"
            "Graph loaded to RDF file can be downloaded here : "
            f'<a href="/data/{relative_graph_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)


class LoadNodesToCDF(Step):
    """
    This step uploads nodes to CDF
    """

    description = "This step uploads nodes to CDF"
    category = CATEGORY
    version = "private-alpha"

    def run(self, cdf_client: CogniteClient, nodes: Nodes) -> FlowMessage:  # type: ignore[override, syntax]
        if nodes.nodes:
            upload_nodes(cdf_client, nodes.nodes, max_retries=2, retry_delay=4)
            return FlowMessage(output_text="CDF nodes uploaded successfully")
        else:
            return FlowMessage(output_text="No nodes to upload!")


class LoadEdgesToCDF(Step):
    """
    This step uploads edges to CDF
    """

    description = "This step uploads edges to CDF"
    category = CATEGORY
    version = "private-alpha"

    def run(self, cdf_client: CogniteClient, edges: Edges) -> FlowMessage:  # type: ignore[override, syntax]
        if edges.edges:
            upload_edges(cdf_client, edges.edges, max_retries=2, retry_delay=4)
            return FlowMessage(output_text="CDF edges uploaded successfully")
        else:
            return FlowMessage(output_text="No edges to upload!")


class GenerateAssetsFromGraph(Step):
    """
    The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object
    """

    description = (
        "The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object"
    )
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="data_set_id", value="", label=("CDF dataset id to which the labels will be added.")),
        Configurable(
            name="asset_external_id_prefix",
            value="",
            label=("Prefix to be added to all asset external ids, default None."),
        ),
        Configurable(
            name="assets_cleanup_type",
            value="nothing",
            options=["nothing", "orphans", "circular", "full"],
            label=(
                "Configures asset cleanup process. Supported options: nothing - no cleanup, \
                    orphans - all orphan assets will be removed, circular - all circular assets will be removed , \
                    full - full cleanup , both orphans and circular assets will be removed. "
            ),
        ),
    ]

    def run(  # type: ignore[override]
        self, rules: RulesData, cdf_client: CogniteClient, solution_graph: SolutionGraph
    ) -> (FlowMessage, CategorizedAssets):  # type: ignore[override, syntax]
        if self.configs is None:
            raise StepNotInitialized(type(self).__name__)
        asset_cleanup_type = self.configs.get("assets_cleanup_type", "nothing")
        data_set_id = int(self.configs["data_set_id"])
        asset_external_id_prefix = self.configs.get("asset_external_id_prefix", None)

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

        rdf_asset_dicts = rdf2assets(
            solution_graph.graph,
            rules.rules,
            data_set_id=data_set_id,
            asset_external_id_prefix=asset_external_id_prefix,
            stop_on_exception=True,
            meta_keys=meta_keys,
        )

        # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
        total_assets_before = cdf_client.assets.aggregate(filter=AssetFilter(data_set_ids=[{"id": data_set_id}]))[
            0
        ].count

        # Label Validation
        labels_before = unique_asset_labels(rdf_asset_dicts.values())
        logging.info(f"Assets have {len(labels_before)} unique labels: {', '.join(sorted(labels_before))}")

        rdf_asset_dicts = cast(dict[str, dict[str, Any]], remove_non_existing_labels(cdf_client, rdf_asset_dicts))

        labels_after = unique_asset_labels(rdf_asset_dicts.values())
        removed_labels = labels_before - labels_after
        logging.info(
            f"Removed {len(removed_labels)} labels as these do not exists in CDF. "
            f"Removed labels: {', '.join(sorted(removed_labels))}"
        )
        ######################

        prom_cdf_resource_stats.labels(resource_type="asset", state="count_before_neat_update").set(total_assets_before)
        logging.info(f"Total count of assets in CDF before upload: { total_assets_before }")

        orphanage_asset_external_id = (
            f"{asset_external_id_prefix}orphanage-{data_set_id}"
            if asset_external_id_prefix
            else f"orphanage-{data_set_id}"
        )
        orphan_assets, circular_assets, parent_children_map = validate_asset_hierarchy(rdf_asset_dicts)

        # There could be assets already under a created orphan assets. Include those in oprhan assets list
        if orphanage_asset_external_id in parent_children_map:
            orphan_assets.extend(parent_children_map[orphanage_asset_external_id])

        orphan_assets_count = len(orphan_assets)
        circular_assets_count = len(circular_assets)
        prom_data_issues_stats.labels(resource_type="circular_assets").set(len(circular_assets))
        prom_data_issues_stats.labels(resource_type="orphan_assets").set(len(orphan_assets))

        if orphan_assets:
            logging.error(f"Found orphaned assets: {', '.join(orphan_assets)}")

            if asset_cleanup_type in ["orphans", "full"]:
                logging.info("Removing orphaned assets and its children")

                def delete_asset_and_children_recursive(asset_id, rdf_asset_dicts, parent_children_map):
                    if asset_id in rdf_asset_dicts:
                        del rdf_asset_dicts[asset_id]

                    if asset_id in parent_children_map:
                        for child_id in parent_children_map[asset_id]:
                            delete_asset_and_children_recursive(child_id, rdf_asset_dicts, parent_children_map)

                def delete_orphan_assets_recursive(orphan_assets, rdf_asset_dicts, parent_children_map):
                    for orphan_asset in orphan_assets:
                        delete_asset_and_children_recursive(orphan_asset, rdf_asset_dicts, parent_children_map)

                # Make sure children, grand-children, great-grandchildren .... are deleted
                delete_orphan_assets_recursive(orphan_assets, rdf_asset_dicts, parent_children_map)

                # delete orphange asset
                if orphanage_asset_external_id in rdf_asset_dicts:
                    del rdf_asset_dicts[orphanage_asset_external_id]

            else:
                # Kill the process if you dont have orphanage asset in your asset hierarchy
                # and inform the user that it is missing !
                if orphanage_asset_external_id not in rdf_asset_dicts:
                    msg = f"You dont have Orphanage asset {orphanage_asset_external_id} in asset hierarchy!"
                    logging.error(msg)
                    return FlowMessage(
                        error_text=msg, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL
                    ), CategorizedAssets(assets={})

                logging.error("Orphaned assets will be assigned to 'Orphanage' root asset")

                for external_id in orphan_assets:
                    rdf_asset_dicts[external_id]["parent_external_id"] = orphanage_asset_external_id
        else:
            logging.info("No orphaned assets found, your assets look healthy !")

        if circular_assets:
            logging.error(f"Found circular dependencies: {circular_assets}")
            if asset_cleanup_type in ["circular", "full"]:
                logging.info("Removing circular assets")
                for circular_path in circular_assets:
                    circular_external_id = circular_path[-1]
                    del rdf_asset_dicts[circular_external_id]
        else:
            logging.info("No circular dependency among assets found, your assets hierarchy look healthy !")

        if orphan_assets or circular_assets:
            orphan_assets, circular_assets, _ = validate_asset_hierarchy(rdf_asset_dicts)
            if circular_assets:
                msg = f"Found circular dependencies: {circular_assets!s}"
                logging.error(msg)
                return FlowMessage(
                    error_text=msg, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL
                ), CategorizedAssets(assets={})
            elif orphan_assets:
                msg = f"Not able to fix orphans: {', '.join(orphan_assets)}"
                logging.error(msg)
                return FlowMessage(
                    error_text=msg, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL
                ), CategorizedAssets(assets={})
            else:
                logging.info("No circular dependency among assets found, your assets hierarchy look healthy !")

        categorized_assets, report = categorize_assets(
            cdf_client, rdf_asset_dicts, data_set_id=data_set_id, return_report=True
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

        msg = f"Total count of assets { len(rdf_asset_dicts) } of which:"
        msg += f"<p> { count_create_assets } to be created </p>"
        msg += f"<p> { count_update_assets } to be updated </p>"
        msg += f"<p> { count_decommission_assets } to be decommissioned </p>"
        msg += f"<p> { count_resurrect_assets } to be resurrected </p>"
        msg += f"<p> Found { orphan_assets_count } orphan assets and"
        msg += f" { circular_assets_count } circular assets </p>"
        if asset_cleanup_type != "nothing":
            msg += " <p> All circular and orphan assets were removed successfully </p>"
        number_of_updates = len(report["decommission"])
        logging.info(f"Total number of updates: {number_of_updates}")

        return FlowMessage(output_text=msg), CategorizedAssets(assets=categorized_assets)


class LoadAssetsToCDF(Step):
    """
    This step uploads categorized assets to CDF
    """

    description = "This step uploads categorized assets to CDF"
    category = CATEGORY
    version = "private-alpha"

    def run(  # type: ignore[override]
        self, cdf_client: CogniteClient, categorized_assets: CategorizedAssets, flow_msg: FlowMessage
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

        # gets first asset available irrespective of its category
        asset_example = next((assets[0] for assets in categorized_assets.assets.values() if assets), None)

        if asset_example:
            data_set_id = cast(Asset, asset_example).data_set_id
            for _ in range(1000):
                total_assets_after = cdf_client.assets.aggregate(
                    filter=AssetFilter(data_set_ids=[{"id": data_set_id}])
                )[0].count
                if total_assets_after >= count_create_assets:
                    break
                logging.info(f"Waiting for assets to be created, current count {total_assets_after}")
                time.sleep(2)

            # UPDATE: 2023-04-05 - correct aggregation of assets in CDF for specific dataset
            total_assets_after = cdf_client.assets.aggregate(filter=AssetFilter(data_set_ids=[{"id": data_set_id}]))[
                0
            ].count

            prom_cdf_resource_stats.labels(resource_type="asset", state="count_after_neat_update").set(
                total_assets_after
            )
            logging.info(f"Total count of assets in CDF after update: { total_assets_after }")
            del categorized_assets.assets  # free up memory after upload .
            return FlowMessage(output_text=f"Total count of assets in CDF after update: { total_assets_after }")
        else:
            return FlowMessage(output_text="No assets to upload!")


class GenerateRelationshipsFromGraph(Step):
    """
    This step generates relationships from the graph and saves them to CategorizedRelationships object
    """

    description = "This step generates relationships from the graph and saves them to CategorizedRelationships object"
    category = CATEGORY
    version = "private-alpha"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="data_set_id", value="", label=("CDF dataset id to which the labels will be added.")),
        Configurable(
            name="relationship_external_id_prefix",
            value="",
            label=("Prefix to be added to all asset external ids, default None."),
        ),
    ]

    def run(  # type: ignore[override]
        self, rules: RulesData, cdf_client: CogniteClient, solution_graph: SolutionGraph
    ) -> (FlowMessage, CategorizedRelationships):  # type: ignore[arg-type, syntax]
        # create, categorize and upload relationships
        data_set_id = int(self.configs["data_set_id"])
        relationship_external_id_prefix = self.configs.get("relationship_external_id_prefix", None)

        rdf_relationships = rdf2relationships(
            solution_graph.graph,
            rules.rules,
            data_set_id=data_set_id,
            relationship_external_id_prefix=relationship_external_id_prefix,
        )

        categorized_relationships = categorize_relationships(cdf_client, rdf_relationships, data_set_id)
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


class LoadRelationshipsToCDF(Step):
    """
    This step uploads relationships to CDF
    """

    description = "This step uploads relationships to CDF"
    category = CATEGORY
    version = "private-alpha"

    def run(  # type: ignore[override, syntax]
        self, client: CogniteClient, categorized_relationships: CategorizedRelationships
    ) -> FlowMessage:
        upload_relationships(client, categorized_relationships.relationships, max_retries=2, retry_delay=4)
        return FlowMessage(output_text="CDF relationships uploaded successfully")
