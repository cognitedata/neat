from typing import Any, cast

import networkx as nx
from ipycytoscape import CytoscapeWidget  # type: ignore
from IPython.display import display

from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.entities._single_value import ViewEntity

from ._state import SessionState


class ShowAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.data_model = ShowDataModelAPI(self._state)


class ShowDataModelAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        if self._state.last_verified_dms_rules:
            digraph = self._generate_dms_di_graph()
            widget = self._generate_widget()
            widget.graph.add_graph_from_networkx(digraph)
            return display(widget)

    def _generate_dms_di_graph(self) -> nx.DiGraph:
        """Generate a DiGraph from the last verified DMS rules."""
        G = nx.DiGraph()

        nodes, edges = self._generate_dms_rules_nodes_and_edges()
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

    def _generate_widget(self):
        """Generates an empty a CytoscapeWidget."""
        widget = CytoscapeWidget()
        widget.layout.height = "500px"

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
                    },
                },
            ]
        )

        return widget
