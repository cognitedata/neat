import logging
from pathlib import Path
from typing import Tuple

from rdflib import RDF, Literal, URIRef
from cognite.neat.constants import PREFIXES
from cognite.neat.graph.transformations.transformer import RuleProcessingReport, domain2app_knowledge_graph
from cognite.neat.rules import parse_rules_from_excel_file
from cognite.neat.rules.exporter.rules2triples import get_instances_as_triples
from cognite.neat.workflows import utils
from cognite.neat.workflows.cdf_store import CdfStore
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem, WorkflowConfigs
from cognite.neat.workflows.steps.step_model import Step

from cognite.client import CogniteClient
from ..data_contracts import RulesData, SolutionGraph, SourceGraph

__all__ = [
    "LoadTransformationRules",
    "TransformSourceToSolutionGraph",
    "LoadInstancesFromRulesToSolutionGraph",
    "LoadDataModelFromRulesToSourceGraph",
]


class LoadTransformationRules(Step):
    description = "The step loads transformation rules from the file or remote location"
    category = "rules"
    configuration_templates = [
        WorkflowConfigItem(
            name="rules.file",
            value="rules.xlsx",
            label="Full name of the rules file",
        ),
        WorkflowConfigItem(name="rules.version", value="", label="Optional version of the rules file"),
    ]

    def run(self, configs: WorkflowConfigs, cdf_store: CdfStore) -> Tuple[FlowMessage, RulesData]:
        rules_file = configs.get_config_item_value("rules.file")
        rules_file_path = Path(self.data_store_path, "rules", rules_file)
        version = configs.get_config_item_value("rules.version", default_value=None)
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

        transformation_rules = parse_rules_from_excel_file(rules_file_path)
        rules_metrics = self.metrics.register_metric(
            "data_model_rules", "Transformation rules stats", m_type="gauge", metric_labels=["component"]
        )
        rules_metrics.labels({"component": "classes"}).set(len(transformation_rules.classes))
        rules_metrics.labels({"component": "properties"}).set(len(transformation_rules.properties))
        logging.info(f"Loaded prefixes {str(transformation_rules.prefixes)} rules from {rules_file_path.name!r}.")
        output_text = f"Loaded {len(transformation_rules.properties)} rules"
        return FlowMessage(output_text=output_text), RulesData(rules=transformation_rules)


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
