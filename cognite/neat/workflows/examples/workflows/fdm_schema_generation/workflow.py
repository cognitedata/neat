import logging
import time
from pathlib import Path

from cognite.client import CogniteClient

from cognite.neat import rules
from cognite.neat.graph import loaders
from cognite.neat.graph.extractors import NeatGraphStore
from cognite.neat.rules.models import TransformationRules
from cognite.neat.workflows.workflow import utils
from cognite.neat.workflows.workflow.base import BaseWorkflow, FlowMessage
from cognite.neat.workflows.workflow.cdf_store import CdfStore


class FDMSchemaGenerationNeatWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.counter = 0
        self.metrics.register_metric("counter_1", "", "counter", ["step"])
        self.metrics.register_metric("gauge_1", "", "gauge", ["step"])
        self.transformation_rules: TransformationRules = None
        self.solution_graph: NeatGraphStore = None
        self.dataset_id: int = 0
        self.upload_meta_object = None

    def step_cleanup(self, flow_msg: FlowMessage = None):
        logging.info("Cleanup")

    def step_error_handler(self, flow_msg: FlowMessage = None):
        logging.info("Error handler")
        return FlowMessage(output_text="Error handleed")

    def step_load_transformation_rules(self, flow_msg: FlowMessage = None):
        # Load rules from file or remote location
        self.upload_meta_object = flow_msg.payload if flow_msg else None
        cdf_store = CdfStore(self.cdf_client, self.dataset_id, rules_storage_path=self.rules_storage_path)

        rules_file = self.get_config_item_value("rules.file")
        rules_file_path = Path(self.rules_storage_path, rules_file)
        version = self.get_config_item_value("rules.version")

        if rules_file_path.exists() and not version:
            logging.info(f"Loading rules from {rules_file_path}")
        elif rules_file_path.exists() and version:
            hash = utils.get_file_hash(rules_file_path)
            if hash != version:
                cdf_store.load_rules_file_from_cdf(rules_file, version)
        else:
            cdf_store.load_rules_file_from_cdf(self.cdf_client, version)

        self.transformation_rules = rules.load_rules_from_excel_file(rules_file_path)
        self.dataset_id = self.transformation_rules.metadata.data_set_id
        logging.info(f"Loaded prefixes {str(self.transformation_rules.prefixes)} rules")
        output_text = f"Loaded {len(self.transformation_rules.properties)} rules"
        logging.info(output_text)
        return FlowMessage(output_text=output_text)

    def step_generate_fdm_schema(self, flow_msg: FlowMessage = None):
        logging.info("Generating FDM schema")
        self.data_model_gql = loaders.rules2graphql_schema(self.transformation_rules)

        default_name = (
            f"{self.transformation_rules.metadata.prefix}-"
            f"v{self.transformation_rules.metadata.version.strip().replace('.', '_')}"
            ".graphql"
        )
        schema_name = self.get_config_item_value("fdm_schema.file", default_name)
        fdm_path = self.rules_storage_path.parent / "data-models" / schema_name

        with open(fdm_path, "w") as fdm_file:
            fdm_file.write(self.data_model_gql)

        output_text = (
            "FDM Schema generated and can be downloaded here : "
            f'<a href="http://localhost:8000/data/data-models/{schema_name}?{time.time()}" '
            f'target="_blank">{schema_name}</a>'
        )

        return FlowMessage(output_text=output_text)
