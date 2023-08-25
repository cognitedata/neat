import logging

from rdflib import Literal, URIRef
from cognite.neat.constants import PREFIXES
from cognite.neat.workflows.model import FlowMessage
from cognite.neat.workflows.steps.data_contracts import SolutionGraph, SourceGraph
from cognite.neat.workflows.steps.step_model import Step, Configurable

__all__ = ["SimpleGraphEntityMatcher"]


class SimpleGraphEntityMatcher(Step):
    description = "The step matches entities in the graph and creates links based on provided configurations"
    category = "contextualization"
    configurables = [
        Configurable(name="source_class", value="", label="Name of the source class"),
        Configurable(name="source_property", value="", label="Name of the source property"),
        Configurable(
            name="source_value_type",
            value="single_value_str",
            label="Type of the value in the source property.Supported options : single_value_str, multi_value_str",
            options=["single_value_str", "multi_value_str"],
        ),
        Configurable(name="target_class", value="", label="Name of the target class"),
        Configurable(name="target_property", value="", label="Name of the target property"),
        Configurable(
            name="relationship_name", value="link", label="Label of the relationship to be created"
        ),
        Configurable(
            name="link_direction",
            value="target_to_source",
            label="Direction of the relationship. Supported options : target_to_source, source_to_target",
        ),
        Configurable(
            name="matching_method",
            value="regexp",
            label="Method to be used for matching. Supported options : exact_match, regexp",
            options=["exact_match", "regexp"],
        ),
        Configurable(
            name="graph_name",
            value="source",
            label="The name of the graph to be used for matching. Supported options : source, solution",
            options=["source", "solution"],
        ),
    ]

    def run(self, graph_store: SolutionGraph | SourceGraph) -> FlowMessage:
        # We can't use the graph_store to get the graph as input parameter directly, resolver might resolve the wrong graph 
        # if both are present in the flow context
        graph_name = self.configs["graph_name"]
        if graph_name == "solution":
            graph_store = self.flow_context["SolutionGraph"]
        else:
            graph_store = self.flow_context["SourceGraph"]
        self.ns = PREFIXES["neat"]
        self.graph_store = graph_store.graph
        new_links_counter = self.simple_entity_matcher(
            source_class=self.configs["source_class"],
            source_property=self.configs["source_property"],
            source_value_type=self.configs["source_value_type"],
            target_class=self.configs["target_class"],
            target_property=self.configs["target_property"],
            relationship_name=self.configs["relationship_name"],
            link_direction=self.configs["link_direction"],
            matching_method=self.configs["matching_method"],
        )
        output_text = f"Matcher has created {new_links_counter} links"
        return FlowMessage(output_text=output_text)

    def simple_entity_matcher(
        self,
        source_class: str,
        source_property: str,
        source_value_type: str = "single_value_str",
        target_class: str = None,
        target_property: str = None,
        relationship_name: str = "link",
        link_direction: str = "target_to_source",  # source_to_target, bidirectional
        matching_method: str = "regexp",  # exact_match, similarity
    ) -> int:
        if source_value_type == "multi_value_str":
            # Split the values and add them as separate triples
            query = f"""
                    SELECT DISTINCT ?source ?source_value
                    WHERE {{
                        ?source rdf:type neat:{source_class} .
                        ?source neat:{source_property} ?source_value .
                    }}
                """
            triples_to_remove = []
            r1 = self.graph_store.query(query)
            result = list(r1)
            for row in result:
                val_split = row[1].split(",")
                if len(val_split) > 1:
                    triples_to_remove.append((row[0], URIRef(self.ns + source_property), row[1]))
                    for val in val_split:
                        self.graph_store.graph.add((row[0], URIRef(self.ns + source_property), Literal(val)))

            for triple in triples_to_remove:
                self.graph_store.graph.remove(triple)

        self.graph_store.graph.commit()
        query = ""
        if matching_method == "exact_match":
            query = f"""
                    SELECT DISTINCT ?source ?target
                    WHERE {{
                        ?source rdf:type neat:{source_class} .
                        ?source neat:{source_property} ?source_value .
                        ?target rdf:type neat:{target_class} .
                        ?target neat:{target_property} ?target_value .
                        FILTER (?source_value = ?target_value)
                    }}
                """
        elif matching_method == "regexp":
            query = f"""
                    SELECT DISTINCT ?source ?target
                    WHERE {{
                        ?source rdf:type neat:{source_class} .
                        ?source neat:{source_property} ?source_value .
                        ?target rdf:type neat:{target_class} .
                        ?target neat:{target_property} ?target_value .
                        FILTER regex(?target_value,?source_value, "i")
                    }}
                """
        else:
            logging.error(f"Unknown matching method {matching_method}")
            return 0
        logging.debug(f"Running matcher query {query}")
        r1 = self.graph_store.query(query)
        result = list(r1)
        logging.debug(f"Identified {len(result)} matches from the graph")
        new_links_counter = 0
        for row in result:
            new_links_counter += 1
            if link_direction == "target_to_source":
                self.graph_store.graph.add((row[1], URIRef(self.ns + relationship_name), row[0]))
            else:
                self.graph_store.graph.add((row[0], URIRef(self.ns + relationship_name), row[1]))

        return new_links_counter
