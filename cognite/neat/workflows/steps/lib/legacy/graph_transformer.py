from typing import ClassVar

from cognite.client import CogniteClient

from cognite.neat.legacy.graph.transformations.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.legacy.rules.exporters._rules2triples import get_instances_as_triples
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["TransformSourceToSolutionGraph"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title() + " [LEGACY]"


class TransformSourceToSolutionGraph(Step):
    """
    The step transforms source graph to solution graph
    """

    description = "The step transforms source graph to solution graph"
    category = CATEGORY
    version = "legacy"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="cdf_lookup_database",
            value="",
            label="Name of the CDF raw database to use for data lookup (rawlookup rules).\
            Applicable only for transformations with rawlookup rules.",
        )
    ]

    def run(  # type: ignore[override, syntax]
        self,
        transformation_rules: RulesData,
        cdf_client: CogniteClient,
        source_graph: SourceGraph,
        solution_graph: SolutionGraph,
    ) -> FlowMessage:
        report = RuleProcessingReport()
        # run transformation and generate new graph
        cdf_lookup_database = self.configs.get("cdf_lookup_database", "")
        solution_graph.graph.set_graph(
            domain2app_knowledge_graph(
                source_graph.graph.get_graph(),
                transformation_rules.rules,
                app_instance_graph=solution_graph.graph.get_graph(),
                extra_triples=get_instances_as_triples(transformation_rules.rules),
                client=cdf_client,
                cdf_lookup_database=cdf_lookup_database,  # change this accordingly!
                processing_report=report,
            )
        )
        return FlowMessage(
            output_text=f"Total processed rules: { report.total_rules } , success: { report.total_success } , \
             no results: { report.total_success_no_results } , failed: { report.total_failed }",
            payload=report,
        )
