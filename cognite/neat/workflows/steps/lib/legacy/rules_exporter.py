import logging
import time
import warnings
from pathlib import Path
from typing import ClassVar, Literal, cast

from cognite.client import data_modeling as dm

import cognite.neat.legacy.graph.extractors._graph_capturing_sheet
from cognite.neat.exceptions import wrangle_warnings
from cognite.neat.legacy.rules import exporters
from cognite.neat.legacy.rules.exporters._rules2dms import DMSSchemaComponents
from cognite.neat.legacy.rules.exporters._rules2graphql import GraphQLSchema
from cognite.neat.legacy.rules.exporters._rules2ontology import Ontology
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows._exceptions import StepNotInitialized
from cognite.neat.workflows.model import FlowMessage, StepExecutionStatus
from cognite.neat.workflows.steps.data_contracts import CogniteClient, DMSSchemaComponentsData, RulesData
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = [
    "ExportDMSSchemaComponentsToYAML",
    "ExportDMSSchemaComponentsToCDF",
    "ExportRulesToGraphQLSchema",
    "ExportRulesToOntology",
    "ExportRulesToSHACL",
    "ExportRulesToGraphCapturingSheet",
    "ExportRulesToExcel",
    "GenerateDMSSchemaComponentsFromRules",
    "DeleteDMSSchemaComponents",
]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title() + " [LEGACY]"


class GenerateDMSSchemaComponentsFromRules(Step):
    """
    This step generates DMS Schema components, such as data model, views, containers, etc. from Rules.
    """

    description = "This step generates DMS Schema components, such as data model, views, containers, etc. from Rules."
    version = "legacy"
    category = CATEGORY

    def run(self, rules: RulesData) -> (FlowMessage, DMSSchemaComponentsData):  # type: ignore[override, syntax]
        data_model = DMSSchemaComponents.from_rules(rules.rules)

        output_text = (
            "DMS Schema Components Generated: "
            f"<li> - {len(data_model.spaces)} spaces</li>"
            f"<li> - {len(data_model.containers)} containers</li>"
            f"<li> - {len(data_model.views)} views</li>"
            f"</ul> which are referred in data model <b><code>{data_model.space}:{data_model.external_id}</code>"
            f"</b>/v=<b><code>{data_model.version}</code></b>"
        )

        # need to store the data model in the step so that it can be used by the next step
        # see GraphQL step

        return FlowMessage(output_text=output_text), DMSSchemaComponentsData(components=data_model)


class ExportDMSSchemaComponentsToYAML(Step):
    """
    This step exports DMS schema components as YAML files
    """

    description = "This step exports DMS schema components as YAML files"
    version = "legacy"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="format",
            value="yaml-dump",
            label="Format of the output files",
            options=["yaml-dump", "cognite-toolkit", "all"],
        ),
    ]

    def run(self, data_model_contract: DMSSchemaComponentsData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        format_ = self.configs["format"]

        staging_dir = self.config.staging_path
        staging_dir.mkdir(parents=True, exist_ok=True)

        if format_ in ["yaml-dump", "all"]:
            base_file_name = (
                f"{data_model_contract.components.space}-"
                f"{data_model_contract.components.external_id}-"
                f"v{data_model_contract.components.version.strip().replace('.', '_')}"
            )

            _container_file_name = f"{base_file_name}-containers.yaml"
            _data_model_file_name = f"{base_file_name}-data-model.yaml"

            container_full_path = staging_dir / _container_file_name
            data_model_full_path = staging_dir / _data_model_file_name

            data_model = dm.DataModelApply(
                space=data_model_contract.components.space,
                external_id=data_model_contract.components.external_id,
                version=data_model_contract.components.version,
                description=data_model_contract.components.description,
                name=data_model_contract.components.name,
                views=list(data_model_contract.components.views.values()),
            )

            containers = dm.ContainerApplyList(data_model_contract.components.containers.values())

            container_full_path.write_text(containers.dump_yaml())
            data_model_full_path.write_text(data_model.dump_yaml())

            output_text = (
                "<p></p>"
                "DMS Schema exported and can be downloaded here : "
                "<p></p>"
                f'- <a href="/data/{self.config.staging_path.name}/{_data_model_file_name}?{time.time()}" '
                f'target="_blank">{_data_model_file_name}</a>'
                "<p></p>"
                f'- <a href="/data/{self.config.staging_path.name}/{_container_file_name}?{time.time()}" '
                f'target="_blank">{_container_file_name}</a>'
            )

            return FlowMessage(output_text=output_text)
        else:
            return FlowMessage(
                error_text=f"Export format <b><code>{format_}</code></b> not implemented!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )


class ExportDMSSchemaComponentsToCDF(Step):
    """
    This step exports generated DMS Schema components to CDF
    """

    description = "This step exports generated DMS Schema components to CDF."
    version = "legacy"
    category = CATEGORY

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="components",
            type="multi_select",
            value="",
            label="Select which DMS schema component(s) to export to CDF",
            options=["space", "container", "view", "data model"],
        ),
        Configurable(
            name="existing_component_handling",
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
            name="multi_space_components_create",
            value="False",
            label=(
                "Whether to create only components belonging to the data model space"
                " (i.e. space define under Metadata sheet of Rules), "
                "or also additionally components outside of the data model space."
            ),
            options=["True", "False"],
        ),
    ]

    def run(self, data_model: DMSSchemaComponentsData, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        existing_component_handling: str = self.configs["existing_component_handling"]
        multi_space_components_create: bool = self.configs["multi_space_components_create"] == "True"
        components_to_create = {key for key, value in self.complex_configs["components"].items() if value}

        if not components_to_create:
            return FlowMessage(
                error_text="No DMS Schema components selected for upload! Please select minimum one!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        logs, errors = data_model.components.to_cdf(
            cdf_client,
            components_to_create=components_to_create,
            existing_component_handling=cast(Literal["skip"], existing_component_handling),
            multi_space_components_create=multi_space_components_create,
            return_report=True,
        )

        report = "# DMS Schema Components Export to CDF\n\n"
        for component, log in logs.items():
            if log:
                report += f"## {component.upper()}\n" + "\n".join(log) + "\n\n"

        report += "\n\n# ERRORS\n\n"
        for component, log in errors.items():
            if log:
                report += f"## {component.upper()}\n" + "\n".join(log) + "\n\n"

        # report
        report_file = "dms_component_creation_report.txt"
        report_dir = self.config.staging_path
        report_dir.mkdir(parents=True, exist_ok=True)
        report_full_path = report_dir / report_file
        report_full_path.write_text(report)

        output_text = (
            "<p></p>"
            "Download DMS Schema Components export "
            f'<a href="/data/staging/{report_file}?{time.time()}" '
            f'target="_blank">report</a>'
        )

        if any(value for value in errors.values()):
            return FlowMessage(error_text=output_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
        else:
            return FlowMessage(output_text=output_text)


class DeleteDMSSchemaComponents(Step):
    """
    This step deletes DMS Schema components
    """

    description = "This step deletes DMS Data model and all underlying containers and views."
    version = "legacy"
    category = CATEGORY

    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="components",
            type="multi_select",
            value="",
            label="Select which DMS schema component(s) to delete",
            options=["space", "container", "view", "data model"],
        ),
        Configurable(
            name="multi_space_components_removal",
            value="False",
            label=(
                "False (default) = Only delete components inside the space referred"
                " in Metadata Sheet of Rules"
                r", True = Delete all components referred to in Rules<\p>"
            ),
            options=["True", "False"],
        ),
    ]

    def run(self, data_model: DMSSchemaComponentsData, cdf_client: CogniteClient) -> FlowMessage:  # type: ignore[override, syntax]
        components_to_remove = {key for key, value in self.complex_configs["components"].items() if value}
        multi_space_components_removal: bool = self.configs["multi_space_components_removal"] == "True"
        if not components_to_remove:
            return FlowMessage(
                error_text="No DMS Schema components selected for deletion! Please select minimum one!",
                step_execution_status=StepExecutionStatus.ABORT_AND_FAIL,
            )

        logs, errors = data_model.components.remove(
            cdf_client,
            components_to_remove=components_to_remove,
            multi_space_components_removal=multi_space_components_removal,
            return_report=True,
        )

        report = "# DMS Schema Components Removal from CDF\n\n"
        for component, log in logs.items():
            if log:
                report += f"## {component.upper()}\n" + "\n".join(log) + "\n\n"

        report += "\n\n# ERRORS\n\n"
        for component, log in errors.items():
            if log:
                report += f"## {component.upper()}\n" + "\n".join(log) + "\n\n"

        # report
        report_file = "dms_component_removal_report.txt"
        report_dir = self.config.staging_path
        report_dir.mkdir(parents=True, exist_ok=True)
        report_full_path = report_dir / report_file
        report_full_path.write_text(report)

        output_text = (
            "<p></p>"
            "Download DMS Schema Components removal "
            f'<a href="/data/staging/{report_file}?{time.time()}" '
            f'target="_blank">report</a>'
        )

        if any(value for value in errors.values()):
            return FlowMessage(error_text=output_text, step_execution_status=StepExecutionStatus.ABORT_AND_FAIL)
        else:
            return FlowMessage(output_text=output_text)


class ExportRulesToGraphQLSchema(Step):
    """
    This step generates GraphQL schema from data model defined in transformation rules
    """

    description = "This step generates GraphQL schema from data model defined in transformation rules."
    version = "legacy"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name",
            value="",
            label=(
                "Name of the GraphQL schema file it must have .graphql extension,"
                " if empty defaults to form `prefix-version.graphql`"
            ),
        ),
        Configurable(name="storage_dir", value="staging", label="Directory to store GraphQL schema file"),
    ]

    def run(self, transformation_rules: RulesData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        data_model_gql = GraphQLSchema.from_rules(transformation_rules.rules, verbose=True).schema

        default_name = (
            f"{transformation_rules.rules.metadata.prefix}-"
            f"v{transformation_rules.rules.metadata.version.strip().replace('.', '_')}"
            ".graphql"
        )

        schema_name = self.configs["file_name"] or default_name

        staging_dir_str = self.configs["storage_dir"]
        staging_dir = self.data_store_path / Path(staging_dir_str)
        staging_dir.mkdir(parents=True, exist_ok=True)
        fdm_model_full_path = staging_dir / schema_name

        fdm_model_full_path.write_text(data_model_gql)

        output_text = (
            "<p></p>"
            "GraphQL Schema generated and can be downloaded here : "
            f'<a href="/data/{staging_dir_str}/{schema_name}?{time.time()}" '
            f'target="_blank">{schema_name}</a>'
        )

        return FlowMessage(output_text=output_text)


class ExportRulesToOntology(Step):
    """
    This step exports Rules to OWL ontology
    """

    description = "This step exports Rules to OWL ontology"
    version = "legacy"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="ontology_file_path",
            value="staging/ontology.ttl",
            label=(
                "Relative path for the ontology file storage, "
                "must end with .ttl ! Will be auto-created if not provided !"
            ),
        )
    ]

    def run(self, rules: RulesData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        # ontology file
        default_path = self.data_store_path / Path(
            f"{rules.rules.metadata.prefix}-"
            f"v{rules.rules.metadata.version.strip().replace('.', '_')}"
            "-ontology.ttl"
        )

        if not self.configs["ontology_file_path"]:
            storage_path = default_path
        else:
            storage_path = self.data_store_path / Path(self.configs["ontology_file_path"])

        storage_path.parent.mkdir(parents=True, exist_ok=True)
        report_file_path = storage_path.parent / f"report_{storage_path.stem}.txt"

        with warnings.catch_warnings(record=True) as validation_warnings:
            ontology = Ontology.from_rules(rules=rules.rules)

        storage_path.write_text(ontology.ontology)
        report_file_path.write_text(generate_exception_report(wrangle_warnings(validation_warnings), "Warnings"))

        relative_ontology_file_path = str(storage_path).split("/data/")[1]

        output_text = (
            "<p></p>"
            "Rules exported to ontology can be downloaded here : "
            f'<a href="/data/{relative_ontology_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)


class ExportRulesToSHACL(Step):
    """
    This step exports Rules to SHACL
    """

    description = "This step exports Rules to SHACL"
    version = "legacy"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="shacl_file_path",
            value="staging/shacl.ttl",
            label=(
                "Relative path for the SHACL file storage, "
                "must end with .ttl ! Will be auto-created if not provided !"
            ),
        )
    ]

    def run(self, rules: RulesData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)

        # ontology file
        default_path = self.data_store_path / Path(
            f"{rules.rules.metadata.prefix}-" f"v{rules.rules.metadata.version.strip().replace('.', '_')}" "-shacl.ttl"
        )

        if not self.configs["shacl_file_path"]:
            storage_path = default_path
        else:
            storage_path = self.data_store_path / Path(self.configs["shacl_file_path"])
        report_file_path = storage_path.parent / f"report_{storage_path.stem}.txt"

        with warnings.catch_warnings(record=True) as validation_warnings:
            ontology = Ontology.from_rules(rules=rules.rules)

        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_text(ontology.constraints)
        report_file_path.write_text(generate_exception_report(wrangle_warnings(validation_warnings), "Warnings"))

        relative_shacl_file_path = str(storage_path).split("/data/")[1]

        output_text = (
            "<p></p>"
            "Rules exported to ontology can be downloaded here : "
            f'<a href="/data/{relative_shacl_file_path}?{time.time()}" '
            f'target="_blank">{storage_path.stem}.ttl</a>'
        )

        return FlowMessage(output_text=output_text)


class ExportRulesToGraphCapturingSheet(Step):
    """
    This step generates graph capturing sheet
    """

    description = "This step generates graph capturing sheet"
    version = "legacy"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="file_name", value="graph_capture_sheet.xlsx", label="File name of the data capture sheet"),
        Configurable(name="auto_identifier_type", value="index-based", label="Type of automatic identifier"),
        Configurable(name="storage_dir", value="staging", label="Directory to store data capture sheets"),
    ]

    def run(self, rules: RulesData) -> FlowMessage:  # type: ignore[override, syntax]
        if self.configs is None or self.data_store_path is None:
            raise StepNotInitialized(type(self).__name__)
        logging.info("Generate graph capture sheet")
        sheet_name = self.configs["file_name"]
        auto_identifier_type = self.configs["auto_identifier_type"]
        staging_dir_str = self.configs["storage_dir"]
        logging.info(f"Auto identifier type {auto_identifier_type}")
        staging_dir = self.data_store_path / Path(staging_dir_str)

        staging_dir.mkdir(parents=True, exist_ok=True)

        data_capture_sheet_path = staging_dir / sheet_name

        cognite.neat.legacy.graph.extractors._graph_capturing_sheet.rules2graph_capturing_sheet(
            rules.rules, data_capture_sheet_path, auto_identifier_type=auto_identifier_type
        )

        output_text = (
            "Data capture sheet generated and can be downloaded here : "
            f'<a href="/data/{staging_dir_str}/{sheet_name}?{time.time()}" target="_blank">'
            f"{sheet_name}</a>"
        )
        return FlowMessage(output_text=output_text)


class ExportRulesToExcel(Step):
    description = "This step export Rules to Excel representation"
    version = "legacy"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="output_file_path", value="rules/custom-rules.xlsx", label="File path to the generated Excel file"
        )
    ]

    def run(self, rules_data: RulesData) -> FlowMessage:  # type: ignore[override, syntax]
        full_path = Path(self.data_store_path) / Path(self.configs["output_file_path"])
        exporters.ExcelExporter.from_rules(rules=rules_data.rules).export_to_file(filepath=full_path)
        return FlowMessage(output_text="Generated Excel file from rules")
