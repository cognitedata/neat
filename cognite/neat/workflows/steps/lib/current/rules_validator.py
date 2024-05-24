import logging
import time
from pathlib import Path
from typing import ClassVar

from cognite.client import CogniteClient

from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.issues.dms import MissingContainerError, MissingSpaceError, MissingViewError
from cognite.neat.rules.issues.formatters import FORMATTER_BY_NAME
from cognite.neat.rules.models import DMSRules, SchemaCompleteness
from cognite.neat.utils import cdf_loaders
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import MultiRuleData
from cognite.neat.workflows.steps.step_model import Configurable, Step

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()

__all__ = [
    "ValidateRulesAgainstCDF",
]


class ValidateRulesAgainstCDF(Step):
    """This steps downloads views and containers from CDF and validates the rules against them

    Note that this only applies to DMSRules
    """

    description = "This steps downloads views and containers from CDF and validates the rules against them."
    category = CATEGORY
    version = "private-beta"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Report Formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
    ]

    def run(self, rules: MultiRuleData, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        if not isinstance(rules.dms, DMSRules):
            return FlowMessage(
                error_text="DMS rules are missing. This step requires DMS rules to be present.",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )
        dms_rules = rules.dms
        if dms_rules.metadata.schema_ is not SchemaCompleteness.partial:
            return FlowMessage(
                error_text="DMS rules are not partial. This step expects DMS rules to be a partial definition "
                "with the rest of the definition being fetched from CDF.",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )
        schema = dms_rules.as_schema()
        errors = schema.validate()
        if not errors:
            return FlowMessage(output_text="Rules are complete and valid. No need to fetch from CDF.")

        missing_spaces = [error.space for error in errors if isinstance(error, MissingSpaceError)]
        missing_views = [error.view for error in errors if isinstance(error, MissingViewError)]
        missing_containers = [error.container for error in errors if isinstance(error, MissingContainerError)]

        retrieved_spaces = cdf_client.data_modeling.spaces.retrieve(missing_spaces).as_write()
        retrieved_containers = cdf_client.data_modeling.containers.retrieve(missing_containers).as_write()
        # Converting read format of views to write format requires to account for parents (implements)
        # Thus we use the loader to convert the views to write format.
        view_loader = cdf_loaders.ViewLoader(cdf_client)
        retrieved_views = [
            view_loader.as_write(view) for view in cdf_client.data_modeling.views.retrieve(missing_views)
        ]
        logging.info(
            f"Retrieved {len(retrieved_spaces)} spaces, {len(retrieved_containers)} containers, "
            f"and {len(retrieved_views)} views from CDF."
        )

        schema.spaces.update({space.space: space for space in retrieved_spaces})
        schema.containers.update({container.as_id(): container for container in retrieved_containers})
        schema.views.update({view.as_id(): view for view in retrieved_views})

        errors = schema.validate()
        if errors:
            output_dir = self.data_store_path / Path("staging")
            report_writer = FORMATTER_BY_NAME[self.configs["Report Formatter"]]()
            report_writer.write_to_file(
                IssueList(errors, title=dms_rules.metadata.name or dms_rules.metadata.external_id),
                file_or_dir_path=output_dir,
            )
            report_file = report_writer.default_file_name
            error_text = (
                "<p></p>"
                f'<a href="/data/staging/{report_file}?{time.time()}" '
                f'target="_blank">The rules failed validation against CDF, click here for report</a>'
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        return FlowMessage(output_text="Rules validated successfully against CDF")
