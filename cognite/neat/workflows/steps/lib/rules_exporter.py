import time
from pathlib import Path
from typing import ClassVar, Literal, cast

from cognite.neat.rules import exporters
from cognite.neat.rules._shared import DMSRules, InformationRules, Rules
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import CogniteClient, MultiRuleData
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["RulesToDMS", "RulesToExcel", "RulesToOntology", "RulesToSHACL", "RulesToSemanticDataModel"]


CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class RulesToDMS(Step):
    """
    This step exports Rules to DMS Schema components in CDF
    """

    description = "This step exports Rules to DMS Schema components in CDF."
    version = "private-beta"
    category = CATEGORY

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Dry run",
            value="False",
            label=("Whether to perform a dry run of the export. "),
            options=["True", "False"],
        ),
        Configurable(
            name="Components",
            type="multi_select",
            value="",
            label="Select which DMS schema component(s) to export to CDF",
            options=["spaces", "containers", "views", "data_models"],
        ),
        Configurable(
            name="Existing component handling",
            value="fail",
            label=(
                "How to handle situation when components being exported in CDF already exist."
                "Fail the step if any component already exists, "
                "Skip the component if it already exists, "
                " or Update the component try to update the component."
            ),
            options=["fail", "skip", "update"],
        ),
        Configurable(
            name="Multi-space components create",
            value="False",
            label=(
                "Whether to create only components belonging to the data model space"
                " (i.e. space define under Metadata sheet of Rules), "
                "or also additionally components outside of the data model space."
            ),
            options=["True", "False"],
        ),
    ]

    def run(self, rules: MultiRuleData, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        existing_components_handling = cast(
            Literal["fail", "update", "skip"], self.configs["Existing component handling"]
        )
        multi_space_components_create: bool = self.configs["Multi-space components create"] == "True"
        components_to_create = {
            cast(Literal["all", "spaces", "data_models", "views", "containers"], key)
            for key, value in self.complex_configs["Components"].items()
            if value
        }
        dry_run = self.configs["Dry run"] == "True"

        if not components_to_create:
            return FlowMessage(
                error_text="No DMS Schema components selected for upload! Please select minimum one!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )
        dms_rules = rules.dms
        if dms_rules is None:
            return FlowMessage(
                error_text="Missing DMS rules in the input data! Please ensure that a DMS rule is provided!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        dms_exporter = exporters.DMSExporter(
            export_components=frozenset(components_to_create),
            include_space=None if multi_space_components_create else {dms_rules.metadata.space},
            existing_handling=existing_components_handling,
        )

        output_dir = self.data_store_path / Path("staging")
        output_dir.mkdir(parents=True, exist_ok=True)
        schema_zip = f"{dms_rules.metadata.external_id}.zip"
        schema_full_path = output_dir / schema_zip
        dms_exporter.export_to_file(schema_full_path, dms_rules)

        report_lines = ["# DMS Schema Export to CDF\n\n"]
        errors = []
        for result in dms_exporter.export_to_cdf(client=cdf_client, rules=dms_rules, dry_run=dry_run):
            report_lines.append(result.as_report_str())
            errors.extend(result.error_messages)

        report_lines.append("\n\n# ERRORS\n\n")
        report_lines.extend(errors)

        output_dir = self.data_store_path / Path("staging")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = "dms_component_creation_report.txt"
        report_full_path = output_dir / report_file
        report_full_path.write_text("\n".join(report_lines))

        output_text = (
            "<p></p>"
            "Download DMS Export Report"
            f'<a href="/data/staging/{report_file}?{time.time()}" '
            f'target="_blank">report</a>'
            "<p></p>"
            "Download DMS exported schema"
            f'- <a href="/data/staging/{schema_zip}?{time.time()}" '
            f'target="_blank">{schema_zip}</a>'
        )

        if errors:
            return FlowMessage(error_text=output_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
        else:
            return FlowMessage(output_text=output_text)


class RulesToExcel(Step):
    """This step exports Rules to Excel serialization"""

    description = "This step exports Rules to Excel serialization."
    version = "private-beta"
    category = CATEGORY

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="Styling",
            value="default",
            label="Styling of the Excel file",
            options=list(exporters.ExcelExporter.style_options),
        ),
    ]

    def run(self, rules: MultiRuleData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        styling = cast(exporters.ExcelExporter.Style, self.configs.get("Styling", "default"))

        excel_exporter = exporters.ExcelExporter(styling=styling)

        rule_instance: Rules
        if rules.domain:
            rule_instance = rules.domain
        elif rules.information:
            rule_instance = rules.information
        elif rules.dms:
            rule_instance = rules.dms
        else:
            output_errors = "No rules provided for export!"
            return FlowMessage(error_text=output_errors, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)

        output_dir = self.data_store_path / Path("staging")
        output_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"exported_rules_{rule_instance.metadata.role.value}.xlsx"
        filepath = output_dir / file_name
        excel_exporter.export_to_file(filepath, rule_instance)

        output_text = (
            "<p></p>"
            f"Download Excel Exported {rule_instance.metadata.role.value} rules: "
            f'- <a href="/data/staging/{file_name}?{time.time()}" '
            f'target="_blank">{file_name}</a>'
        )

        return FlowMessage(output_text=output_text)


class RulesToOntology(Step):
    """
    This step exports Rules to OWL ontology
    """

    description = "This step exports Rules to OWL ontology"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File path",
            value="staging/ontology.ttl",
            label=("Relative path for the ontology file storage, " " It will be auto-created if not provided ! "),
        )
    ]

    def run(self, rules: MultiRuleData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        if not rules.information and not rules.dms:
            return FlowMessage(
                error_text="Rules must be made either by Information Architect or DMS Architect!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        default_path = self.data_store_path / "staging" / _get_default_file_name(rules, "ontology", "ttl")

        storage_path = (
            self.data_store_path / Path(self.configs["File path"]) if self.configs["File path"] else default_path
        )
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        exporter = exporters.OWLExporter()
        exporter.export_to_file(storage_path, cast(InformationRules | DMSRules, rules.information or rules.dms))

        relative_file_path = "/".join(storage_path.relative_to(self.data_store_path).parts)

        output_text = (
            "<p></p>"
            "Rules exported as OWL ontology can be downloaded here : "
            f'<a href="/data/{relative_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)


class RulesToSHACL(Step):
    """
    This step exports Rules to SHACL
    """

    description = "This step exports Rules to SHACL"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File path",
            value="staging/shacl.ttl",
            label=(
                "Relative path for the shacl file storage, "
                "must end with .ttl ! It will be auto-created if not provided !"
            ),
        )
    ]

    def run(self, rules: MultiRuleData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        if not rules.information and not rules.dms:
            return FlowMessage(
                error_text="Rules must be made either by Information Architect or DMS Architect!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        default_path = self.data_store_path / "staging" / _get_default_file_name(rules, "shacl", "ttl")

        storage_path = (
            self.data_store_path / Path(self.configs["File path"]) if self.configs["File path"] else default_path
        )
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        exporter = exporters.SHACLExporter()
        exporter.export_to_file(storage_path, cast(InformationRules | DMSRules, rules.information or rules.dms))

        relative_file_path = "/".join(storage_path.relative_to(self.data_store_path).parts)

        output_text = (
            "<p></p>"
            "Rules exported as SHACL shapes can be downloaded here : "
            f'<a href="/data/{relative_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)


class RulesToSemanticDataModel(Step):
    """
    This step exports Rules to semantic data model
    """

    description = "This step exports Rules to semantic data model (ontology + SHACL)"
    version = "private-beta"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="File path",
            value="staging/semantic-data-model.ttl",
            label=(
                "Relative path for the semantic data model file storage, "
                "must end with .ttl ! It will be auto-created if not provided !"
            ),
        )
    ]

    def run(self, rules: MultiRuleData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        if not rules.information and not rules.dms:
            return FlowMessage(
                error_text="Rules must be made either by Information Architect or DMS Architect!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        default_path = self.data_store_path / "staging" / _get_default_file_name(rules, "semantic-data-model", "ttl")

        storage_path = (
            self.data_store_path / Path(self.configs["File path"]) if self.configs["File path"] else default_path
        )
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        exporter = exporters.SemanticDataModelExporter()
        exporter.export_to_file(storage_path, cast(InformationRules | DMSRules, rules.information or rules.dms))

        relative_file_path = "/".join(storage_path.relative_to(self.data_store_path).parts)

        output_text = (
            "<p></p>"
            "Rules exported as semantic data model (OWL + SHACL) can be downloaded here : "
            f'<a href="/data/{relative_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)


def _get_default_file_name(rules: MultiRuleData, file_category: str = "ontology", extension: str = "ttl") -> str:
    name = rules.information.metadata.prefix if rules.information else cast(DMSRules, rules.dms).metadata.space
    version = rules.information.metadata.version if rules.information else cast(DMSRules, rules.dms).metadata.version
    return f"{name}-v{version.strip().replace('.', '_')}-{file_category}.{extension}"
