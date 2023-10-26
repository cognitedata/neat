import logging
import time
from pathlib import Path
from typing import ClassVar, cast

from prometheus_client import Gauge

from cognite.neat.rules import importer
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows import utils
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import RulesData
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["LoadTransformationRules"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class LoadTransformationRules(Step):
    """
    This step loads transformation rules from the file or remote location
    """

    description = "This step loads transformation rules from the file or remote location"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
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
            label="Full name of the rules file in rules folder. If includes path, \
                it will be relative to the neat data folder",
        ),
        Configurable(name="version", value="", label="Optional version of the rules file"),
    ]

    def run(self, cdf_store: CdfStore) -> (FlowMessage, RulesData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        store = cdf_store
        # rules file
        if self.configs is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        rules_file = Path(self.configs["file_name"])
        if str(rules_file.parent) == ".":
            rules_file_path = Path(self.data_store_path) / "rules" / rules_file
        else:
            rules_file_path = Path(self.data_store_path) / rules_file

        version = self.configs["version"]

        # rules validation
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
                store.load_rules_file_from_cdf(str(rules_file), version)
        else:
            store.load_rules_file_from_cdf(str(rules_file), version)

        raw_rules = importer.ExcelImporter(rules_file_path).to_raw_rules()
        rules, errors, warnings_ = raw_rules.to_rules(return_report=True, skip_validation=False)
        report = generate_exception_report(errors, "Errors") + generate_exception_report(warnings_, "Warnings")

        with report_full_path.open(mode="w") as file:
            file.write(report)

        text_for_report = (
            "<p></p>"
            "Download rules validation report "
            f'<a href="http://localhost:8000/data/{report_dir_str}/{report_file}?{time.time()}" '
            f'target="_blank">here</a>'
        )

        if rules is None:
            return FlowMessage(
                error_text=f"Failed to load transformation rules! {text_for_report}",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        if self.metrics is None:
            raise ValueError(f"Step {type(self).__name__} has not been configured.")
        rules_metrics = cast(
            Gauge,
            self.metrics.register_metric(
                "data_model_rules", "Transformation rules stats", m_type="gauge", metric_labels=["component"]
            ),
        )
        rules_metrics.labels({"component": "classes"}).set(len(rules.classes))
        rules_metrics.labels({"component": "properties"}).set(len(rules.properties))
        logging.info(f"Loaded prefixes {rules.prefixes!s} rules from {rules_file_path.name!r}.")
        output_text = f"<p></p>Loaded {len(rules.properties)} rules! {text_for_report}"

        return FlowMessage(output_text=output_text), RulesData(rules=rules)
