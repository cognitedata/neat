import logging
import time
from pathlib import Path
from typing import ClassVar

from cognite.neat.graph import extractors
from cognite.neat.rules.exporter import rules2graph_sheet
from cognite.neat.utils.utils import add_triples
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph
from cognite.neat.workflows.steps.step_model import Step

__all__ = ["GenerateDataCaptureSpreadsheet", "ProcessDataCaptureSpreadsheetIntoSolutionGraph"]


class GenerateDataCaptureSpreadsheet(Step):
    """
    This step generates data capture spreadsheet from data model defined in rules.
    """

    description = "The step generates data capture spreadsheet from data model defined in rules"
    category = "data_capture"
    configuration_templates: ClassVar[list[WorkflowConfigItem]] = [
        WorkflowConfigItem(
            name="graph_capture.file",
            value="graph_capture_sheet.xlsx",
            label="File name of the data capture sheet",
        ),
        WorkflowConfigItem(
            name="graph_capture_sheet.auto_identifier_type", value="index-based", label="Type of automatic identifier"
        ),
        WorkflowConfigItem(
            name="graph_capture_sheet.storage_dir", value="staging", label="Directory to store data capture sheets"
        ),
    ]

    def run(self, rules: RulesData) -> FlowMessage:
        logging.info("Generate graph capture sheet")
        sheet_name = self.configs.get_config_item_value("graph_capture.file", "graph_capture_sheet.xlsx")
        auto_identifier_type = self.configs.get_config_item_value("graph_capture_sheet.auto_identifier_type", None)
        staging_dir_str = self.configs.get_config_item_value("graph_capture_sheet.storage_dir", "staging")
        logging.info(f"Auto identifier type {auto_identifier_type}")
        staging_dir = self.data_store_path / Path(staging_dir_str)
        staging_dir.mkdir(parents=True, exist_ok=True)
        data_capture_sheet_path = staging_dir / sheet_name

        rules2graph_sheet.rules2graph_capturing_sheet(
            rules.rules, data_capture_sheet_path, auto_identifier_type=auto_identifier_type
        )

        output_text = (
            "Data capture sheet generated and can be downloaded here : "
            f'<a href="http://localhost:8000/data/{staging_dir_str}/{sheet_name}?{time.time()}" target="_blank">'
            f"{sheet_name}</a>"
        )
        return FlowMessage(output_text=output_text)


class ProcessDataCaptureSpreadsheetIntoSolutionGraph(Step):
    """
    This step processes data capture spreadsheet into solution graph.
    """

    description = "The step processes data capture spreadsheet into solution graph"
    category = "data_capture"

    def run(
        self,
        transformation_rules: RulesData,
        solution_graph: SolutionGraph,
    ) -> FlowMessage:
        triggered_flow_message = self.flow_context["StartFlowMessage"]
        data_capture_sheet_path = Path(triggered_flow_message.payload["full_path"])
        logging.info(f"Processing data capture sheet {data_capture_sheet_path}")

        triples = extractors.extract_graph_from_sheet(
            data_capture_sheet_path, transformation_rule=transformation_rules.rules
        )
        add_triples(solution_graph.graph, triples)
        return FlowMessage(output_text="Data capture sheet processed")
