from cognite.client import CogniteClient

from cognite.neat.graph.transformations.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Step

__all__ = ["TransformSourceToSolutionGraph"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class TransformSourceToSolutionGraph(Step):
    """
    The step transforms source graph to solution graph
    """

    description = "The step transforms source graph to solution graph"
    category = CATEGORY

    def run(  # type: ignore[override, syntax]
        self,
        transformation_rules: RulesData,
        cdf_client: CogniteClient,
        source_graph: SourceGraph,
        solution_graph: SolutionGraph,
    ) -> FlowMessage:
        report = RuleProcessingReport()
        # run transformation and generate new graph
        solution_graph.graph.set_graph(
            domain2app_knowledge_graph(
                source_graph.graph.get_graph(),
                transformation_rules.rules,
                app_instance_graph=solution_graph.graph.get_graph(),
                extra_triples=get_instances_as_triples(transformation_rules.rules),
                client=cdf_client,
                cdf_lookup_database=None,  # change this accordingly!
                processing_report=report,
            )
        )
        return FlowMessage(
            output_text=f"Total processed rules: { report.total_rules } , success: { report.total_success } , \
             no results: { report.total_success_no_results } , failed: { report.total_failed }",
            payload=report,
        )
