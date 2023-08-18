import time
from pathlib import Path
from typing import ClassVar

from cognite.neat.rules.exporter.rules2graphql import GraphQLSchema
from cognite.neat.workflows.model import FlowMessage, WorkflowConfigItem
from cognite.neat.workflows.steps.data_contracts import RulesData
from cognite.neat.workflows.steps.step_model import Step

__all__ = ["GenerateGraphQLSchemaFromRules"]


class GenerateGraphQLSchemaFromRules(Step):
    description = "The step generates GraphQL schema from data model defined in rules"
    category = "fdm"
    configuration_templates: ClassVar[list[WorkflowConfigItem]] = [
        WorkflowConfigItem(
            name="fdm_schema.file",
            value="fdm_model.graphql",
            label="Name of the FDM schema file",
        ),
        WorkflowConfigItem(
            name="graph_ql_export.storage_dir", value="staging", label="Directory to store FDM schema file"
        ),
    ]

    def run(self, transformation_rules: RulesData) -> FlowMessage:
        data_model_gql = GraphQLSchema.from_rules(transformation_rules.rules, verbose=True).schema

        default_name = (
            f"{transformation_rules.rules.metadata.prefix}-"
            f"v{transformation_rules.rules.metadata.version.strip().replace('.', '_')}"
            ".graphql"
        )
        schema_name = self.configs.get_config_item_value("fdm_schema.file", default_name)
        staging_dir_str = self.configs.get_config_item_value("graph_ql_export.storage_dir", "staging")
        staging_dir = self.data_store_path / Path(staging_dir_str)
        staging_dir.mkdir(parents=True, exist_ok=True)
        fdm_model_full_path = staging_dir / schema_name

        with fdm_model_full_path.open(mode="w") as fdm_file:
            fdm_file.write(data_model_gql)

        output_text = (
            "FDM Schema generated and can be downloaded here : "
            f'<a href="http://localhost:8000/data/{staging_dir_str}/{schema_name}?{time.time()}" '
            f'target="_blank">{schema_name}</a>'
        )

        return FlowMessage(output_text=output_text)
