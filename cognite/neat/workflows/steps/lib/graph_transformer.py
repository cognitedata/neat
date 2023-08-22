import logging
from pathlib import Path
import time
from openpyxl import Workbook

from rdflib import RDF, Literal, URIRef
from cognite.neat.constants import PREFIXES
from cognite.neat.graph.transformations.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.rules import parse_rules_from_excel_file
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.rules.parser import read_github_sheet_to_workbook, workbook_to_table_by_name, from_tables
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows import utils
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem
from cognite.neat.workflows.steps.step_model import StepCategory, Step

from cognite.client import CogniteClient
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph

__all__ = [
    "TransformSourceToSolutionGraph",
]


class TransformSourceToSolutionGraph(Step):
    description = "The step transforms source graph to solution graph"
    category = StepCategory.GraphTransformer

    def run(
        self,
        transformation_rules: RulesData,
        cdf_client: CogniteClient,
        source_graph: SourceGraph,
        solution_graph: SolutionGraph,
    ) -> FlowMessage:
        solution_graph.graph.drop()
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
