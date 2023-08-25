import logging
import time
import warnings
from pathlib import Path
from typing import ClassVar

from cognite.neat.exceptions import wrangle_warnings
from cognite.neat.rules.exporter import rules2graph_sheet
from cognite.neat.rules.exporter.rules2graphql import GraphQLSchema
from cognite.neat.rules.exporter.rules2ontology import Ontology
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import RulesData
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["GraphQLSchemaFromRules", "OntologyFromRules", "SHACLFromRules", "GraphCaptureSpreadsheetFromRules"]

CATEGORY = __name__.split(".")[-1].replace("_", " ").title()


class GraphQLSchemaFromRules(Step):
    """
    This step generates GraphQL schema from data model defined in transformation rules
    """

    description = "This step generates GraphQL schema from data model defined in transformation rules."
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

    def run(self, transformation_rules: RulesData) -> FlowMessage:
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
            f'<a href="http://localhost:8000/data/{staging_dir_str}/{schema_name}?{time.time()}" '
            f'target="_blank">{schema_name}</a>'
        )

        return FlowMessage(output_text=output_text)


class OntologyFromRules(Step):
    """
    This step generates OWL ontology from data model defined in transformation rules
    """

    description = "This step generates OWL ontology from data model defined in transformation rules."
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name",
            value="",
            label=(
                "Name of the OWL ontology file it must have .ttl extension,"
                " if empty defaults to form `prefix-version-ontology.ttl`"
            ),
        ),
        Configurable(name="storage_dir", value="staging", label="Directory to store the OWL ontology file"),
        Configurable(
            name="store_warnings",
            value="True",
            label="To store warnings while generating ontology",
            options=["True", "False"],
        ),
    ]

    def run(self, transformation_rules: RulesData) -> FlowMessage:
        # ontology file
        default_name = (
            f"{transformation_rules.rules.metadata.prefix}-"
            f"v{transformation_rules.rules.metadata.version.strip().replace('.', '_')}"
            "-ontology.ttl"
        )

        ontology_file = self.configs["file_name"] or default_name

        storage_dir_str = self.configs["storage_dir"]
        storage_dir = self.data_store_path / storage_dir_str
        storage_dir.mkdir(parents=True, exist_ok=True)

        store_warnings = self.configs["store_warnings"].lower() == "true"

        with warnings.catch_warnings(record=True) as validation_warnings:
            ontology = Ontology.from_rules(transformation_rules=transformation_rules.rules)

        with (storage_dir / ontology_file).open(mode="w") as onto_file:
            onto_file.write(ontology.ontology)

        if store_warnings and validation_warnings:
            with (storage_dir / "report.txt").open(mode="w") as report_file:
                report_file.write(generate_exception_report(wrangle_warnings(validation_warnings), "Warnings"))

        output_text = (
            "<p></p>"
            "Ontology generated and can be downloaded here : "
            f'<a href="http://localhost:8000/data/{storage_dir_str}/{ontology_file}?{time.time()}" '
            f'target="_blank">{ontology_file}</a>'
        )

        output_text += (
            (
                "<p></p>"
                " Download conversion report "
                f'<a href="http://localhost:8000/data/{storage_dir_str}/report.txt?{time.time()}" '
                f'target="_blank">here</a>'
            )
            if validation_warnings
            else ""
        )

        return FlowMessage(output_text=output_text)


class SHACLFromRules(Step):
    """
    This step generates SHACL from data model defined in transformation rules
    """

    description = "This step generates SHACL from data model defined in transformation rules"
    category = CATEGORY
    configurables = [
        Configurable(
            name="file_name",
            value="",
            label=(
                "Name of the SHACL file it must have .ttl extension, if "
                "empty defaults to form `prefix-version-shacl.ttl`"
            ),
        ),
        Configurable(name="storage_dir", value="staging", label="Directory to store the SHACL file"),
    ]

    def run(self, transformation_rules: RulesData) -> FlowMessage:
        # ontology file
        default_name = (
            f"{transformation_rules.rules.metadata.prefix}-"
            f"v{transformation_rules.rules.metadata.version.strip().replace('.', '_')}"
            "-shacl.ttl"
        )

        shacl_file = self.configs["file_name"] or default_name

        storage_dir_str = self.configs["storage_dir"]
        storage_dir = self.data_store_path / storage_dir_str
        storage_dir.mkdir(parents=True, exist_ok=True)

        constraints = Ontology.from_rules(transformation_rules=transformation_rules.rules).constraints

        with (storage_dir / shacl_file).open(mode="w") as onto_file:
            onto_file.write(constraints)

        output_text = (
            "<p></p>"
            "SHACL generated and can be downloaded here : "
            f'<a href="http://localhost:8000/data/{storage_dir_str}/{shacl_file}?{time.time()}" '
            f'target="_blank">{shacl_file}</a>'
        )
        return FlowMessage(output_text=output_text)


class GraphCaptureSpreadsheetFromRules(Step):
    """
    This step generates data capture spreadsheet from data model defined in rules
    """

    description = "This step generates data capture spreadsheet from data model defined in rules"
    category = CATEGORY
    configurables: ClassVar[list[Configurable]] = [
        Configurable(
            name="file_name",
            value="graph_capture_sheet.xlsx",
            label="File name of the data capture sheet",
        ),
        Configurable(name="auto_identifier_type", value="index-based", label="Type of automatic identifier"),
        Configurable(name="storage_dir", value="staging", label="Directory to store data capture sheets"),
    ]

    def run(self, rules: RulesData) -> FlowMessage:
        logging.info("Generate graph capture sheet")
        sheet_name = self.configs["file"]
        auto_identifier_type = self.configs["auto_identifier_type"]
        staging_dir_str = self.configs["graph_capture_sheet.storage_dir"]
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
