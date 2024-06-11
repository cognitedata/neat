import time
from pathlib import Path
from typing import ClassVar

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.rules import importers
from cognite.neat.rules.issues.formatters import FORMATTER_BY_NAME
from cognite.neat.rules.models import RoleTypes
from cognite.neat.rules.models.entities import DataModelEntity, DMSUnknownEntity
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import MultiRuleData
from cognite.neat.workflows.steps.step_model import Configurable, Step

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()

__all__ = [
    "ExcelToRules",
    "OntologyToRules",
    "DMSToRules",
    "RulesInferenceFromRdfFile",
]


class ExcelToRules(Step):
    """This step import rules from the Excel file and validates it."""

    description = "This step imports rules from an excel file "
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File name",
            value="",
            label="Full file name of the rules file in the rules folder. \
                If not provided, step will attempt to get file name from payload \
                    of 'File Uploader' step (if exist)",
        ),
        Configurable(
            name="Report formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="Role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, flow_message: FlowMessage) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        file_name = self.configs.get("File name", None)
        full_path = flow_message.payload.get("full_path", None) if flow_message.payload else None

        if file_name:
            rules_file_path = Path(self.data_store_path) / "rules" / file_name
        elif full_path:
            rules_file_path = full_path
        else:
            error_text = "Expected either 'File name' in the step config or 'File uploader' step uploading Excel Rules."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        # if role is None, it will be inferred from the rules file
        role = self.configs.get("Role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        excel_importer = importers.ExcelImporter(rules_file_path)
        rules, issues = excel_importer.to_rules(errors="continue", role=role_enum)

        if rules is None:
            output_dir = self.config.staging_path
            report_writer = FORMATTER_BY_NAME[self.configs["Report formatter"]]()
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


class OntologyToRules(Step):
    """This step import rules from the ontology file (owl) and validates it."""

    description = "This step imports rules from an ontology file "
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File name",
            value="",
            label="Full file name of the ontology file in the rules folder. \
                If not provided, step will attempt to get file name from payload \
                    of 'File Uploader' step (if exist)",
        ),
        Configurable(
            name="Report formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="Role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, flow_message: FlowMessage) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        file_name = self.configs.get("File name", None)
        full_path = flow_message.payload.get("full_path", None) if flow_message.payload else None

        if file_name:
            rules_file_path = self.config.rules_store_path / file_name
        elif full_path:
            rules_file_path = full_path
        else:
            error_text = "Expected either 'File name' in the step config or 'File uploader' step uploading Excel Rules."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        # if role is None, it will be inferred from the rules file
        role = self.configs.get("Role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        ontology_importer = importers.OWLImporter(filepath=rules_file_path)
        rules, issues = ontology_importer.to_rules(errors="continue", role=role_enum)

        if rules is None:
            output_dir = self.config.staging_path
            report_writer = FORMATTER_BY_NAME[self.configs["Report formatter"]]()
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


class DMSToRules(Step):
    """This step imports rules from CDF Data Model"""

    description = "This step imports rules from CDF Data Model"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Data model id",
            value="",
            label="The ID of the Data Model to import. Written at 'my_space:my_data_model(version=1)'",
            type="string",
            required=True,
        ),
        Configurable(
            name="Reference data model id",
            value="",
            label="The ID of the Reference Data Model to import. Written at 'my_space:my_data_model(version=1)'. "
            "This is typically an enterprise data model when you want to import a solution model",
            type="string",
        ),
        Configurable(
            name="Report formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="Role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
    ]

    def run(self, cdf_client: CogniteClient) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        datamodel_id_str = self.configs.get("Data model id")
        if datamodel_id_str is None:
            error_text = "Expected input payload to contain 'Data model id' key."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        datamodel_entity = DataModelEntity.load(datamodel_id_str)
        if isinstance(datamodel_entity, DMSUnknownEntity):
            error_text = (
                f"Data model id should be in the format 'my_space:my_data_model(version=1)' "
                f"or 'my_space:my_data_model', failed to parse space from {datamodel_id_str}"
            )
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
        ref_datamodel_str = self.configs.get("Reference data model id", "")
        ref_model_id: DataModelId | None = None
        if ref_datamodel_str:
            ref_model = DataModelEntity.load(ref_datamodel_str)
            if isinstance(ref_model, DMSUnknownEntity):
                error_text = (
                    f"Reference data model id should be in the format 'my_space:my_data_model(version=1)' "
                    f"or 'my_space:my_data_model', failed to parse space from {ref_datamodel_str}"
                )
                return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
            ref_model_id = ref_model.as_id()

        dms_importer = importers.DMSImporter.from_data_model_id(cdf_client, datamodel_entity.as_id(), ref_model_id)

        # if role is None, it will be inferred from the rules file
        role = self.configs.get("Role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        rules, issues = dms_importer.to_rules(errors="continue", role=role_enum)

        if rules is None:
            output_dir = self.config.staging_path
            report_writer = FORMATTER_BY_NAME[self.configs["Report formatter"]]()
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


class RulesInferenceFromRdfFile(Step):
    """This step infers rules from the RDF file which contains knowledge graph."""

    description = "This step infers rules from the RDF file which contains knowledge graph"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File path",
            value="staging/knowledge_graph.ttl",
            label=("Relative path to the RDF file to be used for inference"),
        ),
        Configurable(
            name="Report formatter",
            value=next(iter(FORMATTER_BY_NAME.keys())),
            label="The format of the report for the validation of the rules",
            options=list(FORMATTER_BY_NAME),
        ),
        Configurable(
            name="Role",
            value="infer",
            label="For what role Rules are intended?",
            options=["infer", *RoleTypes.__members__.keys()],
        ),
        Configurable(
            name="Maximum number of instances to process",
            value="-1",
            label=(
                "Maximum number of instances to process"
                " to infer rules from the RDF file. Default -1 means all instances."
            ),
        ),
    ]

    def run(self, flow_message: FlowMessage) -> (FlowMessage, MultiRuleData):  # type: ignore[syntax, override]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        file_path = self.configs.get("File path", None)
        full_path = flow_message.payload.get("full_path", None) if flow_message.payload else None

        try:
            max_number_of_instance = int(self.configs.get("Maximum number of instances to process", -1))
        except ValueError:
            error_text = "Maximum number of instances to process should be an integer value"
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        if file_path:
            rdf_file_path = self.data_store_path / Path(file_path)
        elif full_path:
            rdf_file_path = full_path
        else:
            error_text = "Expected either 'File name' in the step config or 'File uploader' step uploading Excel Rules."
            return FlowMessage(error_text=error_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        # if role is None, it will be inferred from the rules file
        role = self.configs.get("Role")
        role_enum = None
        if role != "infer" and role is not None:
            role_enum = RoleTypes[role]

        inference_importer = importers.InferenceImporter.from_rdf_file(
            rdf_file_path, max_number_of_instance=max_number_of_instance
        )
        rules, issues = inference_importer.to_rules(errors="continue", role=role_enum)

        if rules is None:
            output_dir = self.config.staging_path
            report_writer = FORMATTER_BY_NAME[self.configs["Report formatter"]]()
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
