from typing import ClassVar

from cognite.neat.graph.transformations.entity_matcher import simple_entity_matcher
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Configurable, Step

__all__ = ["SimpleGraphEntityMatcher"]


class SimpleGraphEntityMatcher(Step):
    description = "The step matches entities in the graph and creates links based on provided configurations"
    category = "contextualization"
    configurables: ClassVar[list[Configurable]] = [
        Configurable(name="source_class", value="", label="Name of the source class"),
        Configurable(name="source_property", value="", label="Name of the source property"),
        Configurable(
            name="source_value_type",
            value="single_value_str",
            label="Type of the value in the source property.Propery can have single value \
              or multiple values separated by comma.",
            options=["single_value_str", "multi_value_str"],
        ),
        Configurable(name="target_class", value="", label="Name of the target class"),
        Configurable(name="target_property", value="", label="Name of the target property"),
        Configurable(name="relationship_name", value="link", label="Label of the relationship to be created"),
        Configurable(
            name="link_direction",
            value="target_to_source",
            label="Direction of the relationship.",
            options=["target_to_source", "source_to_target"],
        ),
        Configurable(
            name="matching_method",
            value="regexp",
            label="Method to be used for matching. Supported options .",
            options=["exact_match", "regexp"],
        ),
        Configurable(
            name="graph_name",
            value="source",
            label="The name of the graph to be used for matching.",
            options=["source", "solution"],
        ),
        Configurable(
            name="link_namespace",
            value="http://purl.org/cognite/neat#",
            label="The namespace of the link to be created",
        ),
    ]

    def run(self, graph_store: SolutionGraph | SourceGraph) -> FlowMessage:
        # We can't use the graph_store to get the graph as input parameter directly,
        # resolver might resolve the wrong graph
        # if both are present in the flow context
        graph_name = self.configs["graph_name"]
        if graph_name == "solution":
            graph_store = self.flow_context["SolutionGraph"]
        else:
            graph_store = self.flow_context["SourceGraph"]
        self.graph_store = graph_store.graph
        new_links_counter = simple_entity_matcher(
            graph_store=self.graph_store,
            source_class=self.configs["source_class"],
            source_property=self.configs["source_property"],
            source_value_type=self.configs["source_value_type"],
            target_class=self.configs["target_class"],
            target_property=self.configs["target_property"],
            relationship_name=self.configs["relationship_name"],
            link_direction=self.configs["link_direction"],
            matching_method=self.configs["matching_method"],
            link_namespace=self.configs["link_namespace"],
        )
        output_text = f"Matcher has created {new_links_counter} links"
        return FlowMessage(output_text=output_text)
