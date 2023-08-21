import logging
from pathlib import Path
import time
from openpyxl import Workbook

from rdflib import RDF, Literal, URIRef
from cognite.neat.constants import PREFIXES
from cognite.neat.graph.transformations.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.rules import parse_rules_from_excel_file
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.rules.parser import read_github_sheet_to_workbook, _workbook_to_table_by_name, from_tables
from cognite.neat.utils.utils import generate_exception_report
from cognite.neat.workflows import utils
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem
from cognite.neat.workflows.steps.step_model import Step

from cognite.client import CogniteClient
from cognite.neat.workflows.steps.data_contracts import RulesData, SolutionGraph, SourceGraph

__all__ = [
    "LoadTransformationRules",
    "DownloadTransformationRulesFromGitHub",
    "TransformSourceToSolutionGraph",
    "LoadInstancesFromRulesToSolutionGraph",
    "LoadDataModelFromRulesToSourceGraph",
]


class LoadTransformationRules(Step):
    description = "The step loads transformation rules from the file or remote location"
    category = "rules"
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
        logging.info(f"Loaded prefixes {str(transformation_rules.prefixes)} rules from {rules_file_path.name!r}.")
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
    description = "The step fetches and stores transformation rules from private Github repository"
    category = "rules"
    configuration_templates = [
        WorkflowConfigItem(
            name="github.filepath",
            value="",
            label="File path to Transformation Rules stored on Github",
        ),
        WorkflowConfigItem(
            name="github.personal_token",
            value="",
            label="Insert Github Personal Access Token which allows fetching file from Github",
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

    def run(self, cdf_store: CdfStore) -> (FlowMessage, RulesData):
        github_filepath = self.configs.get_config_item_value("github.filepath")
        github_personal_token = self.configs.get_config_item_value("github.personal_token")
        github_owner = self.configs.get_config_item_value("github.owner")
        github_repo = self.configs.get_config_item_value("github.repo")
        github_branch = self.configs.get_config_item_value("github.branch", "main")

        workbook: Workbook = read_github_sheet_to_workbook(
            github_filepath, github_personal_token, github_owner, github_repo, github_branch
        )

        workbook.save(Path(self.data_store_path, "rules", Path(github_filepath).name))

        output_text = (
            "<p></p>"
            " Downloaded rules from "
            f'<a href="https://api.github.com/repos/{github_owner}/{github_repo}'
            f'/contents/{github_filepath}?ref={github_branch}" '
            f'target="_blank">Github</a>'
        )

        output_text += (
            "<p></p>"
            " Downloaded rules accessible locally "
            f'<a href="http://localhost:8000/data/rules/{Path(github_filepath).name}?{time.time()}" '
            f'target="_blank">here</a>'
        )

        return FlowMessage(output_text=output_text), RulesData(rules=from_tables(_workbook_to_table_by_name(workbook)))


class TransformSourceToSolutionGraph(Step):
    description = "The step transforms source graph to solution graph"
    category = "transformation"

    def run(
        self,
        transformation_rules: RulesData,
        cdf_client: CogniteClient,
        source_graph: SourceGraph,
        solution_graph: SolutionGraph,
    ) -> FlowMessage:
        solution_graph.graph.drop()
        report = RuleProcessingReport()
        # run transformation and generate new graph
        solution_graph.graph.set_graph(
            domain2app_knowledge_graph(
                source_graph.graph.get_graph(),
                transformation_rules.rules,
                app_instance_graph=solution_graph.graph.get_graph(),
                extra_triples=get_instances_as_triples(transformation_rules.rules),
                client=cdf_client,
                cdf_lookup_database=None,  # change this accordingly!
                processing_report=report,
            )
        )
        return FlowMessage(
            output_text=f"Total processed rules: { report.total_rules } , success: { report.total_success } , \
             no results: { report.total_success_no_results } , failed: { report.total_failed }",
            payload=report,
        )


class LoadInstancesFromRulesToSolutionGraph(Step):
    description = "The step loads instances from rules file into solution graph."
    category = "graph_loader"

    def run(self, transformation_rules: RulesData, solution_graph: SolutionGraph) -> FlowMessage:
        triples = get_instances_as_triples(transformation_rules.rules)
        instance_ids = {triple[0] for triple in triples}
        output_text = f"Loaded {len(instance_ids)} instances out of"

        try:
            for triple in triples:
                solution_graph.graph.graph.add(triple)
        except Exception as e:
            logging.error("Not able to load instances to source graph")
            raise e

        output_text = f"Loaded {len(triples)} statements defining"
        output_text += f" {len(instance_ids)} instances"
        return FlowMessage(output_text=output_text)


class LoadDataModelFromRulesToSourceGraph(Step):
    description = "The step loads data model from rules file into source graph."
    category = "graph_loader"

    def run(self, transformation_rules: RulesData, source_graph: SourceGraph) -> FlowMessage:
        ns = PREFIXES["neat"]
        clases = transformation_rules.rules.classes
        properties = transformation_rules.rules.properties
        counter = 0
        for class_name, class_def in clases.items():
            rdf_instance_id = URIRef(ns + "_" + class_def.class_id)
            source_graph.graph.graph.add((rdf_instance_id, URIRef(ns + "Name"), Literal(class_name)))
            source_graph.graph.graph.add((rdf_instance_id, RDF.type, URIRef(ns + class_def.class_id)))
            if class_def.parent_class:
                source_graph.graph.graph.add(
                    (rdf_instance_id, URIRef(ns + "hasParent"), URIRef(ns + "_" + class_def.parent_class))
                )
            counter += 1

        for property_name, property_def in properties.items():
            rdf_instance_id = URIRef(ns + "_" + property_def.class_id)
            source_graph.graph.graph.add(
                (rdf_instance_id, URIRef(ns + property_def.property_id), Literal(property_def.expected_value_type))
            )
            if property_def.expected_value_type not in ("string", "integer", "float", "boolean"):
                source_graph.graph.graph.add(
                    (rdf_instance_id, URIRef(ns + "connectedTo"), URIRef(ns + "_" + property_def.expected_value_type))
                )
            counter += 1

        output_text = f"Loaded {counter} classes into source graph"
        return FlowMessage(output_text=output_text)
