import time
from pathlib import Path
from typing import ClassVar

from cognite.client import CogniteClient

from cognite.neat.rules import importers
from cognite.neat.rules.models._rules import RoleTypes
from cognite.neat.rules.models._rules._types import DataModelEntity, Undefined
from cognite.neat.rules.validation.formatters import FORMATTER_BY_NAME
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import MultiRuleData
from cognite.neat.workflows.steps.step_model import Configurable, Step

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()

__all__ = [
    "ImportExcelToRules",
    "ImportDMSToRules",
]


class ImportExcelToRules(Step):
    """This step import rules from the Excel file and validates it."""

    description = "This step imports rules from an excel file "
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Report Formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, flow_message: FlowMessage) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        try:
            rules_file_path = flow_message.payload["full_path"]
        except (KeyError, TypeError):
            error_text = "Expected input payload to contain 'full_path' key."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
        # if role is None, it will be inferred from the rules file
        role = self.configs.get("role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        excel_importer = importers.ExcelImporter(rules_file_path)
        rules, issues = excel_importer.to_rules(role=role_enum, errors="continue")

        if rules is None:
            output_dir = self.data_store_path / Path("staging")
            report_writer = FORMATTER_BY_NAME[self.configs["Report Formatter"]]()
            report_writer.write_to_file(issues, file_or_dir_path=output_dir)
            report_file = report_writer.default_file_name
            error_text = (
                "<p></p>"
                f'<a href="/data/staging/{report_file}?{time.time()}" '
                f'target="_blank">Failed to validate rules, click here for report</a>'
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        output_text = "Rules validation passed successfully!"

        return FlowMessage(output_text=output_text), MultiRuleData.from_rules(rules)


class ImportDMSToRules(Step):
    """This step imports rules from CDF Data Model"""

    description = "This step imports rules from CDF Data Model"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Data Model ID",
            value="",
            label="The ID of the Data Model to import. Written at 'my_space:my_data_model(version=1)'",
            type="string",
            required=True,
        ),
        Configurable(
            name="Report Formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, cdf_client: CogniteClient) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        datamodel_id_str = self.configs.get("Data Model ID")
        if datamodel_id_str is None:
            error_text = "Expected input payload to contain 'Data Model ID' key."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        datamodel_entity = DataModelEntity.from_raw(datamodel_id_str)
        if datamodel_entity.space is Undefined:
            error_text = (
                f"Data Model ID should be in the format 'my_space:my_data_model(version=1)' "
                f"or 'my_space:my_data_model', failed to parse space from {datamodel_id_str}"
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        dms_importer = importers.DMSImporter.from_data_model_id(cdf_client, datamodel_entity.as_id())

        # if role is None, it will be inferred from the rules file
        role = self.configs.get("role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        rules, issues = dms_importer.to_rules(role=role_enum, errors="continue")

        if rules is None:
            output_dir = self.data_store_path / Path("staging")
            report_writer = FORMATTER_BY_NAME[self.configs["Report Formatter"]]()
            report_writer.write_to_file(issues, file_or_dir_path=output_dir)
            report_file = report_writer.default_file_name
            error_text = (
                "<p></p>"
                f'<a href="/data/staging/{report_file}?{time.time()}" '
                f'target="_blank">Failed to validate rules, click here for report</a>'
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        output_text = "Rules import and validation passed successfully!"

        return FlowMessage(output_text=output_text), MultiRuleData.from_rules(rules)
