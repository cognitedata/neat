import logging
import time
from pathlib import Path
from typing import ClassVar, cast

from openpyxl import Workbook
from prometheus_client import Gauge

from cognite.neat.rules.parser import (
    from_tables,
    parse_rules_from_excel_file,
    read_github_sheet_to_workbook,
    workbook_to_table_by_name,
)
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows import utils
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import CDFStoreData, RulesData
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["LoadTransformationRules", "DownloadTransformationRulesFromGitHub"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()

__all__ = ["LoadTransformationRules", "DownloadTransformationRulesFromGitHub"]


class LoadTransformationRules(Step[RulesData]):
    """
    This step loads transformation rules from the file or remote location
    """

    description = "This step loads transformation rules from the file or remote location"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="validate_rules",
            value="True",
            label="To generate validation report",
            options=["True", "False"],
        ),
        Configurable(
            name="validation_report_storage_dir",
            value="rules_validation_report",
            label="Directory to store validation report",
        ),
        Configurable(
            name="validation_report_file",
            value="rules_validation_report.txt",
            label="File name to store validation report",
        ),
        Configurable(
            name="file_name",
            value="rules.xlsx",
            label="Full name of the rules file",
        ),
        Configurable(name="version", value="", label="Optional version of the rules file"),
    ]

    def run(self, cdf_store: CDFStoreData) -> tuple[FlowMessage, RulesData]:
        store = cdf_store.store
        # rules file
        if self.configs is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        rules_file = self.configs["file_name"]
        rules_file_path = Path(self.data_store_path, "rules", rules_file)
        version = self.configs["version"]

        # rules validation
        validate_rules = self.configs["validate_rules"].lower() == "true"
        report_file = self.configs["validation_report_file"]
        report_dir_str = self.configs["validation_report_storage_dir"]
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
                store.load_rules_file_from_cdf(rules_file, version)
        else:
            store.load_rules_file_from_cdf(rules_file, version)

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

        if transformation_rules is None:
            raise ValueError(f"Failed to load transformation rules from {rules_file_path.name!r}.")

        if self.metrics is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        rules_metrics = cast(
            Gauge,
            self.metrics.register_metric(
                "data_model_rules", "Transformation rules stats", m_type="gauge", metric_labels=["component"]
            ),
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


class DownloadTransformationRulesFromGitHub(Step[RulesData]):
    """
    This step fetches and stores transformation rules from private Github repository
    """

    description = "This step fetches and stores transformation rules from private Github repository"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="github.filepath",
            value="",
            label="File path to Transformation Rules stored on Github",
        ),
        Configurable(
            name="github.personal_token",
            value="",
            label="Github Personal Access Token which allows fetching file from private Github repository",
            type="password",
        ),
        Configurable(
            name="github.owner",
            value="",
            label="Github repository owner, also know as github organization",
        ),
        Configurable(
            name="github.repo",
            value="",
            label="Github repository from which Transformation Rules file is being fetched",
        ),
        Configurable(
            name="github.branch",
            value="main",
            label="Github repository branch from which Transformation Rules file is being fetched",
        ),
    ]

    def run(self, *_) -> tuple[FlowMessage, RulesData]:
        if self.configs is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        github_filepath = self.configs["github.filepath"]
        github_personal_token = self.configs["github.personal_token"]
        github_owner = self.configs["github.owner"]
        github_repo = self.configs["github.repo"]
        github_branch = self.configs["github.branch"]
        local_file_name = self.configs["rules.file"] or Path(github_filepath).name

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
