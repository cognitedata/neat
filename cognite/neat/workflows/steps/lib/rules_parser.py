import logging
import time
from pathlib import Path

from openpyxl import Workbook

from cognite.neat.rules.parser import (
    from_tables,
    parse_rules_from_excel_file,
    read_github_sheet_to_workbook,
    workbook_to_table_by_name,
)
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows import utils
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem
from cognite.neat.workflows.steps.data_contracts import RulesData
from cognite.neat.workflows.steps.step_model import Step, StepCategory


class LoadTransformationRules(Step):
    """
    This step loads transformation rules from the file or remote location
    """

    description = "This step loads transformation rules from the file or remote location"
    category = StepCategory.RulesParser
    configuration_templates = [
        WorkflowConfigItem(
            name="rules.validate_rules",
            value="True",
            label="To generate validation report",
        ),
        WorkflowConfigItem(
            name="rules.validation_report_storage_dir",
            value="rules_validation_report",
            label="Directory to store validation report",
        ),
        WorkflowConfigItem(
            name="rules.validation_report_file",
            value="rules_validation_report.txt",
            label="File name to store validation report",
        ),
        WorkflowConfigItem(
            name="rules.file",
            value="rules.xlsx",
            label="Full name of the rules file",
        ),
        WorkflowConfigItem(name="rules.version", value="", label="Optional version of the rules file"),
    ]

    def run(self, cdf_store: CdfStore) -> (FlowMessage, RulesData):
        # rules file
        rules_file = self.configs.get_config_item_value("rules.file")
        rules_file_path = Path(self.data_store_path, "rules", rules_file)
        version = self.configs.get_config_item_value("rules.version", default_value=None)

        # rules validation
        validate_rules = self.configs.get_config_item_value("rules.validate_rules", "true").lower() == "true"
        report_file = self.configs.get_config_item_value("rules.validation_report_file", "rules_validation.txt")
        report_dir_str = self.configs.get_config_item_value(
            "rules.validation_report_storage_dir", "rules_validation_reports"
        )
        report_dir = self.data_store_path / Path(report_dir_str)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_full_path = report_dir / report_file

        if not rules_file_path.exists():
            logging.info(f"Rules files doesn't exist in local fs {rules_file_path}")

        if rules_file_path.exists() and not version:
            logging.info(f"Loading rules from {rules_file_path}")
        elif rules_file_path.exists() and version:
            hash = utils.get_file_hash(rules_file_path)
            if hash != version:
                cdf_store.load_rules_file_from_cdf(rules_file, version)
        else:
            cdf_store.load_rules_file_from_cdf(rules_file, version)

        if validate_rules:
            transformation_rules, validation_errors, validation_warnings = parse_rules_from_excel_file(
                rules_file_path, return_report=True
            )
            report = generate_exception_report(validation_errors, "Errors") + generate_exception_report(
                validation_warnings, "Warnings"
            )

            with report_full_path.open(mode="w") as file:
                file.write(report)
        else:
            transformation_rules = parse_rules_from_excel_file(rules_file_path)

        rules_metrics = self.metrics.register_metric(
            "data_model_rules", "Transformation rules stats", m_type="gauge", metric_labels=["component"]
        )
        rules_metrics.labels({"component": "classes"}).set(len(transformation_rules.classes))
        rules_metrics.labels({"component": "properties"}).set(len(transformation_rules.properties))
        logging.info(f"Loaded prefixes {transformation_rules.prefixes!s} rules from {rules_file_path.name!r}.")
        output_text = f"<p></p>Loaded {len(transformation_rules.properties)} rules!"

        output_text += (
            (
                "<p></p>"
                " Download rules validation report "
                f'<a href="http://localhost:8000/data/{report_dir_str}/{report_file}?{time.time()}" '
                f'target="_blank">here</a>'
            )
            if validate_rules
            else ""
        )

        return FlowMessage(output_text=output_text), RulesData(rules=transformation_rules)


class DownloadTransformationRulesFromGitHub(Step):
    """
    This step fetches and stores transformation rules from private Github repository
    """

    description = "This step fetches and stores transformation rules from private Github repository"
    category = StepCategory.RulesParser
    configuration_templates = [
        WorkflowConfigItem(
            name="github.filepath",
            value="",
            label="File path to Transformation Rules stored on Github",
        ),
        WorkflowConfigItem(
            name="github.personal_token",
            value="",
            label="Github Personal Access Token which allows fetching file from private Github repository",
        ),
        WorkflowConfigItem(
            name="github.owner",
            value="",
            label="Github repository owner, also know as github organization",
        ),
        WorkflowConfigItem(
            name="github.repo",
            value="",
            label="Github repository from which Transformation Rules file is being fetched",
        ),
        WorkflowConfigItem(
            name="github.branch",
            value="main",
            label="Github repository branch from which Transformation Rules file is being fetched",
        ),
    ]

    def run(self) -> (FlowMessage, RulesData):
        github_filepath = self.configs.get_config_item_value("github.filepath")
        github_personal_token = self.configs.get_config_item_value("github.personal_token")
        github_owner = self.configs.get_config_item_value("github.owner")
        github_repo = self.configs.get_config_item_value("github.repo")
        github_branch = self.configs.get_config_item_value("github.branch", "main")
        local_file_name = self.configs.get_config_item_value("rules.file") or Path(github_filepath).name

        logging.info(f"{local_file_name} local file name")

        workbook: Workbook = read_github_sheet_to_workbook(
            github_filepath, github_personal_token, github_owner, github_repo, github_branch
        )

        workbook.save(Path(self.data_store_path, "rules", local_file_name))

        output_text = (
            "<p></p>"
            f" Downloaded rules file <b>{Path(github_filepath).name}</b> from:"
            f'<p><a href="https://github.com/{github_owner}/{github_repo}/tree/{github_branch}"'
            f'target="_blank">https://github.com/{github_owner}/{github_repo}/tree/{github_branch}</a></p>'
        )

        output_text += (
            "<p></p>"
            " Downloaded rules accessible locally under file name "
            f'<a href="http://localhost:8000/data/rules/{local_file_name}?{time.time()}" '
            f'target="_blank">{local_file_name}</a>'
        )

        return FlowMessage(output_text=output_text), RulesData(rules=from_tables(workbook_to_table_by_name(workbook)))
