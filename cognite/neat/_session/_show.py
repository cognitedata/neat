import random
from typing import Any, cast

import networkx as nx
from ipycytoscape import CytoscapeWidget  # type: ignore
from IPython.display import display

from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.entities._single_value import ClassEntity, ViewEntity
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._state import SessionState


class ShowAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.data_model = ShowDataModelAPI(self._state)
        self.instances = ShowInstanceAPI(self._state)


class ShowInstanceAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        if not self._state.store.graph:
            print("No graph data available.")
            return None

        widget = CytoscapeWidget()
        widget.layout.height = "700px"

        G, types = self._get_instance_di_graph_and_types()
        widget_style = self._generate_cytoscape_widget_style(types)
        widget.set_style(widget_style)

        widget.graph.add_graph_from_networkx(G)
        print("Max of 100 nodes and edges are displayed, which are randomly selected.")

        return display(widget)

    def _get_instance_di_graph_and_types(self):
        query = """
        SELECT ?s ?p ?o ?ts ?to WHERE {
            ?s ?p ?o .
            FILTER(isIRI(?o))  # Example filter to check if ?o is an IRI (object type)
            FILTER(BOUND(?o))
            FILTER(?p != rdf:type)

            ?s a ?ts .
            ?o a ?to .
        }
        LIMIT 100
        """

        G = nx.DiGraph()

        types = set()

        for (
            s,
            p,
            o,
            s_type,
            o_type,
        ) in self._state.store.graph.query(query):
            s = remove_namespace_from_uri(s)
            p = remove_namespace_from_uri(p)
            o = remove_namespace_from_uri(o)
            s_type = remove_namespace_from_uri(s_type)
            o_type = remove_namespace_from_uri(o_type)

            G.add_node(s, label=s, type=s_type)
            G.add_node(o, label=o, type=o_type)
            G.add_edge(s, o, label=p)

            types.add(s_type)
            types.add(o_type)

        return G, types

    def _generate_cytoscape_widget_style(self, types: list[str]) -> list[dict]:
        widget_style = [
            {
                "selector": "edge",
                "style": {
                    "width": 1,
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                    "label": "data(label)",
                    "font-size": "8px",
                    "line-color": "black",
                    "target-arrow-color": "black",
                },
            },
        ]

        colors = self._generate_hex_colors(len(types))

        for i, type_ in enumerate(types):
            widget_style.append(self._generate_node_cytoscape_style(type_, colors[i]))

        return widget_style

    @staticmethod
    def _generate_hex_colors(n: int) -> list[str]:
        """Generate a list of N random HEX color codes."""
        hex_colors = []
        for _ in range(n):
            color = f"#{random.randint(0, 0xFFFFFF):06x}"
            hex_colors.append(color)
        return hex_colors

    @staticmethod
    def _generate_node_cytoscape_style(type_: str, color: str) -> dict:
        template = {
            "css": {
                "content": "data(label)",
                "text-valign": "center",
                "color": "black",
                "font-size": "10px",
                "width": "mapData(score, 0, 1, 10, 50)",
                "height": "mapData(score, 0, 1, 10, 50)",
            },
        }

        template["selector"] = f'node[type = "{type_}"]'  # type: ignore
        template["css"]["background-color"] = color

        return template


class ShowDataModelAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        if not self._state.last_verified_dms_rules and not self._state.last_verified_information_rules:
            print("No rules have been verified yet.")
            return None

        if self._state.last_verified_dms_rules:
            nodes, edges = self._generate_dms_rules_nodes_and_edges()
        elif self._state.last_verified_information_rules:
            nodes, edges = self._generate_info_rules_nodes_and_edges()

        digraph = self._generate_dms_di_graph(nodes, edges)
        widget = self._generate_widget()
        widget.graph.add_graph_from_networkx(digraph)
        return display(widget)

    def _generate_dms_di_graph(self, nodes: list[str], edges: list[tuple]) -> nx.DiGraph:
        """Generate a DiGraph from the last verified DMS rules."""
        G = nx.DiGraph()

        G.add_nodes_from(nodes)
        G.add_edges_from(edges)

        for node in G.nodes:
            G.nodes[node]["label"] = node

        return G

    def _generate_dms_rules_nodes_and_edges(self) -> tuple[list[str], list[tuple[str, str, dict]]]:
        """Generate nodes and edges for the last verified DMS rules for DiGraph."""

        nodes = []
        edges = []

        for prop_ in cast(DMSRules, self._state.last_verified_dms_rules).properties:
            nodes.append(prop_.view.suffix)

            if prop_.connection and isinstance(prop_.value_type, ViewEntity):
                label = f"{prop_.property_} [{0 if prop_.nullable else 1}..{ '' if prop_.is_list else 1}]"
                edges.append((prop_.view.suffix, prop_.value_type.suffix, {"label": label}))

        for view in cast(DMSRules, self._state.last_verified_dms_rules).views:
            nodes.append(view.view.suffix)

            if view.implements:
                for implement in view.implements:
                    edges.append((view.view.suffix, implement.suffix, {"label": "implements"}))

        return nodes, edges

    def _generate_info_rules_nodes_and_edges(
        self,
    ) -> tuple[list[str], list[tuple[str, str, dict]]]:
        """Generate nodes and edges for the last verified Information rules for DiGraph."""

        nodes = []
        edges = []

        for prop_ in cast(InformationRules, self._state.last_verified_information_rules).properties:
            nodes.append(prop_.class_.suffix)
            if prop_.type_ == EntityTypes.object_property:
                label = f"{prop_.property_} [{1 if prop_.is_mandatory else 0}..{ '' if prop_.is_list else 1}]"
                edges.append(
                    (
                        prop_.class_.suffix,
                        cast(ClassEntity, prop_.value_type).suffix,
                        {"label": label},
                    )
                )

        for class_ in cast(InformationRules, self._state.last_verified_information_rules).classes:
            nodes.append(class_.class_.suffix)

            if class_.parent:
                for parent in class_.parent:
                    edges.append((class_.class_.suffix, parent.suffix, {"label": "subClassOf"}))

        return nodes, edges

    def _generate_widget(self):
        """Generates an empty a CytoscapeWidget."""
        widget = CytoscapeWidget()
        widget.layout.height = "700px"

        widget.set_style(
            [
                {
                    "selector": "node",
                    "css": {
                        "content": "data(label)",
                        "text-valign": "center",
                        "color": "black",
                        "background-color": "#33C4FF",
                        "font-size": "10px",
                        "width": "mapData(score, 0, 1, 10, 50)",
                        "height": "mapData(score, 0, 1, 10, 50)",
                    },
                },
                {
                    "selector": "edge",
                    "style": {
                        "width": 1,
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier",
                        "label": "data(label)",
                        "font-size": "8px",
                        "line-color": "black",
                        "target-arrow-color": "black",
                    },
                },
                {
                    "selector": 'edge[label = "subClassOf"]',
                    "style": {
                        "line-color": "grey",
                        "target-arrow-color": "grey",
                        "line-style": "dashed",
                        "font-size": "8px",
                    },
                },
                {
                    "selector": 'edge[label = "implements"]',
                    "style": {
                        "line-color": "grey",
                        "target-arrow-color": "grey",
                        "line-style": "dashed",
                        "font-size": "8px",
                    },
                },
            ]
        )

        return widget
